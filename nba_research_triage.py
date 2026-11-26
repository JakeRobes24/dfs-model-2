"""Full-pool research triage; never changes scores or eligibility."""
import json
import math
import pandas as pd



def paired_gap_breakdown(daily_points, daily_minutes, encoded):
    """Split each matched provider's point difference into time and rate effects.

    Use symmetric attribution (average of the two rates/minutes) so the terms
    sum exactly to the point gap. Never borrow minutes from another provider.
    The weighted average describes only providers with paired data.
    """
    empty = dict(paired_source_count=0, paired_point_gap=None, time_effect=None,
                 rate_effect=None, paired_projected_fppm=None, paired_gap_driver='Paired evidence unavailable')
    try:
        p, m = float(daily_points), float(daily_minutes)
        notes = json.loads(encoded)
    except (ValueError, TypeError):
        return empty
    if not (math.isfinite(p) and p >= 0 and math.isfinite(m) and 0 < m <= 60
            and isinstance(notes, list)):
        return empty
    rows = []
    families = set()
    for note in notes:
        try:
            points, minutes, weight = (float(note[k]) for k in ('points', 'paired_minutes', 'weight'))
            family = note['family']
            if not isinstance(family, str) or not family or family in families:
                return empty
            if not (0 <= points <= 150 and 0 < minutes <= 60 and 0 < weight <= 1):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        families.add(family)
        rate, baseline_rate = points / minutes, p / m
        time_effect = (minutes - m) * (rate + baseline_rate) / 2
        rate_effect = (rate - baseline_rate) * (minutes + m) / 2
        rows.append((weight, points - p, time_effect, rate_effect, rate))
    if not rows:
        return empty
    total = sum(row[0] for row in rows)
    gap, time, rate = (sum(row[0] * row[i] for row in rows) / total for i in (1, 2, 3))
    if abs(time) < 1 and abs(rate) < 1:
        driver = 'Small paired effects'
    elif time * rate < 0:
        driver = 'Offsetting time and rate effects'
    elif abs(time) >= 2 * abs(rate):
        driver = 'Mainly projected minutes'
    elif abs(rate) >= 2 * abs(time):
        driver = 'Mainly projected production rate'
    else:
        driver = 'Mixed minutes and production rate'
    return dict(paired_source_count=len(rows), paired_point_gap=gap, time_effect=time,
                rate_effect=rate, paired_projected_fppm=sum(row[0] * row[4] for row in rows) / total,
                paired_gap_driver=driver)


def disagreement_queue(scored):
    """Separate provider agreement against DAILY from provider conflict.

    Priority is a transparent research ordering, not a projection or GPP score.
    """
    required = {'fanduel_id','fanduel_name','eligible','projected_fd_points',
                'adjusted_fd_points','independent_fd_points','projection_source_count',
                'projection_source_spread','projected_minutes','independent_minutes',
                'recent_mpg','blend_status','salary'}
    if not required <= set(scored):
        raise ValueError('Full reviewed pool required for disagreement triage.')
    q = scored.loc[scored.eligible.eq(True)].copy()
    q['point_gap'] = q.independent_fd_points - q.projected_fd_points
    q['minute_gap'] = q.independent_minutes - q.projected_minutes
    q['history_gap'] = pd.to_numeric(q.recent_mpg, errors='coerce') - q.projected_minutes
    q['point_gap_pct'] = 100 * q.point_gap / q.projected_fd_points.where(q.projected_fd_points.gt(0))
    q['review_reason'] = ''
    for mask, label in [
        (q.history_gap.abs().gt(5), 'Recent rotation differs from DAILY'),
        (q.minute_gap.abs().gt(5), 'Independent minutes differ from DAILY'),
        (q.point_gap.abs().ge(5) & q.projection_source_count.lt(2), 'Single-source point discrepancy'),
        (q.point_gap.abs().ge(5) & q.projection_source_count.ge(2) &
         q.projection_source_spread.lt(5), 'Agreeing providers differ from DAILY'),
        (q.projection_source_spread.ge(5), 'Independent point providers conflict'),
        (~q.adjusted_fd_points.gt(0), 'Missing usable projection'),
    ]:
        q.loc[mask, 'review_reason'] += label + '; '
    q = q.loc[q.review_reason.ne('')].copy()
    q['research_priority'] = q[['point_gap','minute_gap','history_gap','projection_source_spread']].abs().max(axis=1)
    q.loc[~q.adjusted_fd_points.gt(0), 'research_priority'] = float('inf')
    q['review_reason'] = q.review_reason.str.rstrip('; ')
    breakdown = [paired_gap_breakdown(row.projected_fd_points, row.projected_minutes,
                                      getattr(row, 'projection_sources_json', '[]'))
                 for row in q.itertuples()]
    fields = ['paired_source_count', 'paired_point_gap', 'time_effect', 'rate_effect', 'paired_projected_fppm', 'paired_gap_driver']
    for field in fields:
        q[field] = [row[field] for row in breakdown]
    columns = ['fanduel_id','fanduel_name','salary','projected_fd_points','independent_fd_points',
               'adjusted_fd_points','point_gap','point_gap_pct','projection_source_count',
               'projection_source_spread','projected_minutes','independent_minutes','recent_mpg',
               'minute_gap','history_gap','blend_status','review_reason', *fields, 'research_priority']
    return q.sort_values(['research_priority','fanduel_id'], ascending=[False,True])[columns]


def attach_rate_context(queue, summaries):
    """Compare paired projections with observed, minutes-weighted box-score production.

    Descriptive evidence only: recent historical rates are not forecasts, and
    cannot isolate the effects of matchup, usage or future lineup changes.
    """
    result = queue.copy()
    fields = {'FD points per minute': 'observed_fppm',
              'Games with complete FD stats': 'observed_rate_games',
              'Minutes with complete FD stats': 'observed_rate_minutes',
              'Shot/FT/turnover opportunities per minute': 'observed_opportunity_rate',
              'Box-score sources': 'observed_rate_sources'}
    if summaries.empty:
        for target in fields.values():
            result[target] = None
    else:
        if summaries.fanduel_id.duplicated().any():
            raise ValueError('Historical rate evidence must identify unique players.')
        result = result.merge(summaries[['fanduel_id', *fields]].rename(columns=fields),
                              on='fanduel_id', how='left', validate='one_to_one')
    daily_minutes = pd.to_numeric(result.projected_minutes, errors='coerce')
    result['daily_fppm'] = result.projected_fd_points / daily_minutes.where(daily_minutes.gt(0))
    observed = pd.to_numeric(result.observed_fppm, errors='coerce')
    paired = pd.to_numeric(result.paired_projected_fppm, errors='coerce')
    result['daily_rate_vs_history'] = result.daily_fppm - observed
    result['paired_rate_vs_history'] = paired - observed
    games = pd.to_numeric(result.observed_rate_games, errors='coerce')
    minutes = pd.to_numeric(result.observed_rate_minutes, errors='coerce')
    result['historical_rate_context'] = 'No complete historical rate evidence'
    result.loc[observed.notna(), 'historical_rate_context'] = 'Small observed sample'
    result.loc[observed.notna() & games.ge(3) & minutes.ge(60),
               'historical_rate_context'] = 'Recent observed rate; role and matchup still require review'
    return result


def team_opportunity_review(scored, audit, as_of):
    """Flag eligible teammates for review after official OUT/role confirmation.

    A confirmation is not necessarily new information. Post-confirmation source
    timestamps establish timing, not that providers incorporated the news.
    Never assign vacated minutes, adjust points, or infer a replacement role.
    """
    columns = ['fanduel_id', 'Player', 'Team', 'Game', 'Confirmed events',
               'Latest confirmation UTC', 'Minutes families since confirmation',
               'Points families since confirmation', 'Adjusted minutes',
               'Adjusted FD', 'Opportunity review']
    needed = {'fanduel_id', 'fanduel_name', 'team', 'game', 'eligible',
              'prelock_status', 'prelock_starter', 'prelock_role',
              'adjusted_minutes', 'adjusted_fd_points', 'projection_sources_json'}
    audit_fields = {'fanduel_id', 'official', 'review', 'observed_at',
                    'status', 'starter', 'minutes', 'independent_group'}
    if not needed <= set(scored) or not audit_fields <= set(audit):
        raise ValueError('Use a reviewed contest pool and its audited source evidence.')
    if scored.fanduel_id.isna().any() or not scored.fanduel_id.is_unique:
        raise ValueError('Opportunity review requires unique contest IDs.')
    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        raise ValueError('Opportunity review requires a timezone-aware as-of time.')
    notes = audit.loc[audit.review.eq('Reviewed') & audit.fanduel_id.isin(scored.fanduel_id)].copy()
    notes['time'] = pd.to_datetime(notes.observed_at, utc=True, errors='coerce', format='mixed')
    notes = notes.loc[notes.time.le(cutoff) & notes.time.ge(cutoff-pd.Timedelta(hours=6))]
    official = notes.loc[notes.official.eq(True)]
    by_id = dict(tuple(notes.groupby('fanduel_id')))
    official_by_id = dict(tuple(official.groupby('fanduel_id')))
    events = {}
    for player in scored.itertuples():
        own = official_by_id.get(player.fanduel_id)
        if own is None:
            continue
        key = (player.team, player.game)
        if not all(isinstance(v, str) and v.strip() for v in key):
            continue
        for field, allowed in [('status', {'out','inactive','suspended','available','probable','questionable','doubtful'}),
                               ('starter', {'starter','bench'})]:
            values = own[field].astype(str).str.casefold()
            decisions = own.loc[values.isin(allowed)]
            if decisions.empty:
                continue
            stamp = decisions.time.max()
            latest = set(decisions.loc[decisions.time.eq(stamp), field].astype(str).str.casefold())
            if len(latest) != 1:
                continue
            value = next(iter(latest))
            if field == 'status':
                relevant = value in {'out','inactive','suspended'} and value == player.prelock_status
            else:
                opposite = {'starter':'projected bench', 'bench':'projected starter'}[value]
                relevant = value == player.prelock_starter and str(player.prelock_role).casefold() == opposite
            if relevant:
                events.setdefault(key, []).append((stamp, f'{player.fanduel_name}: {value}'))
    rows = []
    for player in scored.loc[scored.eligible.eq(True)].itertuples():
        group = events.get((player.team, player.game), [])
        if not group:
            continue
        stamp = max(t for t, _ in group)
        own = by_id.get(player.fanduel_id)
        minute_count = 0
        if own is not None:
            mins = own.loc[own.time.ge(stamp) & own.independent_group.fillna('').ne('')].copy()
            mins['value'] = pd.to_numeric(mins.minutes, errors='coerce')
            mins = mins.loc[mins.value.between(0,48)]
            latest = mins.loc[mins.time.eq(mins.groupby('independent_group').time.transform('max'))]
            minute_count = int(latest.groupby('independent_group').value.nunique().eq(1).sum())
        point_families = {}
        try:
            estimates = json.loads(player.projection_sources_json)
            if isinstance(estimates, list):
                for estimate in estimates:
                    try:
                        family = estimate['family']
                        t = pd.Timestamp(estimate['observed_at'])
                        points = float(estimate['points'])
                        if (isinstance(family,str) and family.strip() and t.tzinfo is not None
                                and stamp <= t <= cutoff and math.isfinite(points) and 0 <= points <= 150):
                            point_families.setdefault(family, []).append((t,points))
                    except (ValueError,TypeError,KeyError,OverflowError):
                        continue
        except (ValueError,TypeError):
            pass
        point_count = sum(len({v for t,v in values if t == max(x[0] for x in values)}) == 1
                          for values in point_families.values())
        reasons = []
        if minute_count < 2:
            reasons.append('Recheck minutes')
        if point_count < 2:
            reasons.append('Recheck production')
        if not reasons:
            reasons.append('Check whether refreshed providers incorporated news')
        rows.append([player.fanduel_id,player.fanduel_name,player.team,player.game,
                     ' | '.join(sorted({label for _,label in group})),stamp.isoformat(),
                     minute_count,point_count,player.adjusted_minutes,player.adjusted_fd_points,
                     '; '.join(reasons)])
    return pd.DataFrame(rows, columns=columns).sort_values(
        ['Minutes families since confirmation','Points families since confirmation','fanduel_id']
    ).reset_index(drop=True)


def paired_source_coverage(scored, as_of, *, include_details=False):
    """Report actual fresh same-provider points/minutes coverage, not a score.

    Counts are an upper bound on shadow-policy support: injury, rate agreement
    and team confirmation gates are evaluated separately by the shadow model.
    """
    if not {'fanduel_id','eligible','projection_sources_json'} <= set(scored):
        raise ValueError('Paired source coverage requires reviewed projection evidence.')
    if scored.fanduel_id.isna().any() or not scored.fanduel_id.is_unique:
        raise ValueError('Coverage requires unique player IDs.')
    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        raise ValueError('Coverage requires a timezone-aware as-of timestamp.')
    from slate_research import POINT_SOURCE_GROUPS
    providers = {}
    players = []
    details = {}
    for row in scored.loc[scored.eligible.astype(str).str.lower().eq('true')].itertuples():
        accepted = {}
        try:
            notes = json.loads(row.projection_sources_json)
            if not isinstance(notes,list):
                raise ValueError
            for note in notes:
                try:
                    family = note['family']
                    stamp = pd.Timestamp(note['observed_at'])
                    points = float(note['points'])
                    if (not isinstance(family,str) or not family.strip()
                            or POINT_SOURCE_GROUPS.get(note.get('source')) != family or pd.isna(stamp)
                            or stamp.tzinfo is None or not cutoff-pd.Timedelta(hours=6) <= stamp <= cutoff
                            or not math.isfinite(points) or not 0 < points <= 150):
                        continue
                    minutes = note.get('paired_minutes')
                    paired = False
                    if minutes is not None:
                        try:
                            m = float(minutes)
                            paired = math.isfinite(m) and 0 < m <= 48 and 0 < points/m <= 5
                        except (ValueError,TypeError,OverflowError):
                            pass
                    accepted.setdefault(family,[]).append((stamp,points,paired,minutes if paired else None))
                except (ValueError,TypeError,KeyError,OverflowError):
                    continue
        except (ValueError,TypeError):
            pass
        families = []
        for family, records in accepted.items():
            latest = max(t[0] for t in records)
            current = [t for t in records if t[0] == latest]
            # Repeated or conflicting latest family records are not independent.
            if len(current) != 1:
                continue
            paired = current[0][2]
            counts = providers.setdefault(family,[0,0])
            counts[0] += 1
            counts[1] += int(paired)
            if paired:
                families.append(family)
                stamp, points, _, minutes = current[0]
                details.setdefault(row.fanduel_id, []).append((family, stamp, points, float(minutes)))
        players.append({'fanduel_id':row.fanduel_id,'Paired providers':len(families),
                        'Paired source families':' · '.join(sorted(families))})
    provider_rows = [{'Provider':family,'Fresh point players':counts[0],
                      'Fresh paired players':counts[1]}
                     for family,counts in sorted(providers.items())]
    coverage = (pd.DataFrame(players,columns=['fanduel_id','Paired providers','Paired source families']),
                pd.DataFrame(provider_rows,columns=['Provider','Fresh point players','Fresh paired players']))
    return (*coverage, details) if include_details else coverage


def large_minutes_disagreement_shadow(scored, as_of):
    """Isolate time and scoring-rate hypotheses on the same support.

    One paired provider can corroborate a large rotation discrepancy. Point
    forecasts and rates are experimental sensitivity cases, never optimizer inputs.
    """
    _, _, details = paired_source_coverage(scored, as_of, include_details=True)
    cutoff = pd.Timestamp(as_of)
    date = cutoff.tz_convert('America/New_York').date()
    rows = []
    columns = ['fanduel_id', 'family', 'observed_at', 'provider_minutes', 'recent_mpg',
               'reviewed_minutes', 'estimated_minutes', 'reviewed_rate', 'provider_rate',
               'time_only_fd', 'time_and_rate_fd', 'capped_time_only_fd']
    for player in scored.itertuples():
        paired = details.get(player.fanduel_id, [])
        if (len(paired) != 1 or player.identity_match not in {'exact', 'known_alias'}
                or player.minutes_method != 'DAILY_only_unverified'
                or str(player.injury_flag).strip().casefold() not in {'', 'nan'}
                or str(player.prelock_status).strip().casefold() not in {'', 'nan', 'available'}
                or str(player.prelock_role).strip().casefold() not in {'', 'nan', 'projected starter', 'projected bench'}
                or any(x in str(player.prelock_change).casefold() for x in ('limit', 'restrict', 'conflict', 'starter:', 'bench:'))
                or player.history_source != 'NBA official box scores'):
            continue
        family, observed_at, points, source_minutes = paired[0]
        try:
            reviewed_minutes, reviewed_points, recent, games = map(
                float, (player.adjusted_minutes, player.adjusted_fd_points, player.recent_mpg, player.history_games))
            daily_minutes, daily_points = map(float, (player.projected_minutes, player.projected_fd_points))
            history_date = pd.Timestamp(player.history_latest).date()
            if (not all(map(math.isfinite, (reviewed_minutes, reviewed_points, recent, games, daily_minutes, daily_points)))
                    or not date-pd.Timedelta(days=21) <= history_date < date
                    or not (0 < daily_minutes <= 48 and 0 < daily_points <= 150
                            and 0 < reviewed_minutes <= 48 and 0 < reviewed_points <= 150
                            and 0 < recent <= 48 and games >= 3)):
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        midpoint = (source_minutes + recent)/2
        change = midpoint - reviewed_minutes
        if abs(recent - source_minutes) > 3 or abs(change) < 5:
            continue
        reviewed_rate, provider_rate = reviewed_points/reviewed_minutes, points/source_minutes
        if not 0 < reviewed_rate <= 5:
            continue
        time_only = midpoint*reviewed_rate
        combined = midpoint*(.75*reviewed_rate+.25*provider_rate)
        capped = (reviewed_minutes+max(-4.,min(4.,change)))*reviewed_rate
        rows.append((player.fanduel_id, family, observed_at.isoformat(), source_minutes, recent,
                     reviewed_minutes, midpoint, reviewed_rate, provider_rate, time_only, combined, capped))
    return pd.DataFrame(rows, columns=columns)


LARGE_MINUTES_POLICIES = {
    'Large minutes discrepancy, time only': 'time_only_fd',
    'Large minutes discrepancy, time and provider rate': 'time_and_rate_fd',
    'Large minutes discrepancy, capped time only': 'capped_time_only_fd',
}
LARGE_MINUTES_CAPTURE_FIELDS = (
    'shadow_large_minutes_policy', 'shadow_large_minutes_as_of',
    *('shadow_large_minutes_' + field for field in LARGE_MINUTES_POLICIES.values()),
)


def compare_frozen_large_minutes(frame):
    """Score all three frozen forecasts on exactly the same verified played rows."""
    rows = [{'Policy': label, 'Paired players': 0} for label in LARGE_MINUTES_POLICIES]
    base = ('daily_points', 'adjusted_fd_points', 'actual_points')
    required = {*LARGE_MINUTES_CAPTURE_FIELDS, *base, 'replay_captured_at_utc',
                'eligible', 'verified_outcome', 'nba_source'}
    if not required <= set(frame):
        return pd.DataFrame(rows)
    reviewed = pd.to_datetime(frame.shadow_large_minutes_as_of, format='mixed', utc=True, errors='coerce')
    captured = pd.to_datetime(frame.replay_captured_at_utc, format='mixed', utc=True, errors='coerce')
    forecasts = list(LARGE_MINUTES_CAPTURE_FIELDS[2:])
    values = frame[[*base, *forecasts]].apply(pd.to_numeric, errors='coerce')
    baseline = (frame.eligible.eq(True) & frame.verified_outcome.eq('played')
                & frame.nba_source.fillna('').ne('') & values.daily_points.map(math.isfinite))
    paired = values.loc[baseline & (reviewed <= captured) & frame.shadow_large_minutes_policy.eq('2026-11-26')
                        & values.apply(lambda col: col.map(math.isfinite)).all(axis=1)]
    for row, column in zip(rows, forecasts):
        row['Eligible played with baseline'] = int(baseline.sum())
        row['Paired players'] = len(paired)
        if not paired.empty:
            errors = paired.drop(columns='actual_points').sub(paired.actual_points, axis=0)
            mae = errors.abs().mean()
            row.update({'DAILY MAE': mae.daily_points, 'Reviewed MAE': mae.adjusted_fd_points,
                        'Shadow MAE': mae[column], 'MAE improvement vs reviewed': mae.adjusted_fd_points-mae[column],
                        'Shadow bias': errors[column].mean()})
    return pd.DataFrame(rows)
