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
