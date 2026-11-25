"""Post-slate source-specific accuracy; frozen forecasts only, no weight updates."""
import json
from collections import defaultdict
from itertools import combinations

import pandas as pd

from nba_distribution_review import bounded, timestamp
from slate_research import POINT_SOURCE_GROUPS, RW_MINUTES, NBA_HOUSE, PROPSIMS, ROTOGRINDERS

MINUTE_SOURCES = {RW_MINUTES: 'rotowire', NBA_HOUSE: 'nba-house',
                  PROPSIMS: 'propsims', ROTOGRINDERS: 'rotogrinders'}
FIELDS = ['fanduel_id','provider','metric','role','outcome','forecast','actual',
          'daily','reviewed','observed_at','source_error','daily_error','reviewed_error']


def records(value):
    try:
        data = json.loads(value)
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def review_sources(replay):
    """Compare accepted forecasts on their own matched baseline samples.

    Minutes use played players only; verified DNPs count as zero for points.
    Independent provider counts are not a reason to change live scoring.
    """
    if not {'projection_sources_json','replay_evidence_json'} & set(replay):
        return pd.DataFrame(columns=FIELDS)
    required = {'fanduel_id','eligible','verified_outcome','actual_points','actual_minutes',
                'daily_points','daily_minutes','adjusted_fd_points','adjusted_minutes',
                'replay_captured_at_utc','replay_cutoff_utc','replay_timing','replay_before_full_slate_tip'}
    if not required <= set(replay) or not replay.fanduel_id.is_unique or replay.fanduel_id.isna().any():
        raise ValueError('Source review requires a unique frozen replay.')
    output = []
    for row in replay.itertuples():
        if (str(row.eligible).lower() != 'true' or str(row.replay_before_full_slate_tip).lower() != 'true'
                or row.replay_timing != 'before_scheduled_tip'
                or row.verified_outcome not in ('played','did_not_play')):
            continue
        capture, tip = timestamp(row.replay_captured_at_utc), timestamp(row.replay_cutoff_utc)
        if capture is None or tip is None or capture >= tip:
            continue
        notes = records(getattr(row,'replay_evidence_json',None))
        # A later official status/starting confirmation invalidates earlier estimates,
        # matching the conservative pre-lock consensus policy.
        news = [stamp for note in notes
                if note.get('official') is True
                and (str(note.get('status','')).lower() in
                     {'out','inactive','suspended','available','probable','questionable','doubtful'}
                     or str(note.get('starter','')).lower() in {'starter','bench'})
                and (stamp := timestamp(note.get('observed_at'))) is not None and stamp <= capture]
        earliest = max([capture-pd.Timedelta(hours=6), *news])
        estimates = defaultdict(list)
        def add(family, metric, stamp, value, high):
            value = bounded(value,0,high)
            if value is not None and stamp is not None and earliest <= stamp <= capture:
                estimates[family,metric].append((stamp,value))
        for note in records(getattr(row,'projection_sources_json',None)):
            family = POINT_SOURCE_GROUPS.get(note.get('source'))
            if family is None or family != note.get('family'):
                continue
            stamp = timestamp(note.get('observed_at'))
            add(family,'FD points',stamp,note.get('points'),150)
            add(family,'Minutes',stamp,note.get('paired_minutes'),48)
        for note in notes:
            family = MINUTE_SOURCES.get(note.get('source'))
            if family is None or family != note.get('independent_group') or note.get('official') is not False:
                continue
            add(family,'Minutes',timestamp(note.get('observed_at')),note.get('minutes'),48)
        role = getattr(row,'prelock_starter','')
        role = role if role in ('starter','bench') else 'unconfirmed'
        for (family,metric), candidates in sorted(estimates.items()):
            latest = max(stamp for stamp,_ in candidates)
            values = {value for stamp,value in candidates if stamp == latest}
            if len(values) != 1:
                continue
            forecast = next(iter(values))
            if metric == 'Minutes':
                if row.verified_outcome != 'played':
                    continue
                actual = bounded(row.actual_minutes,0,90)
                daily = bounded(row.daily_minutes,0,60)
                reviewed = bounded(row.adjusted_minutes,0,60)
            else:
                actual = (0.0 if row.verified_outcome == 'did_not_play'
                          else bounded(row.actual_points,-150,300))
                daily = bounded(row.daily_points,0,150)
                reviewed = bounded(row.adjusted_fd_points,0,150)
            if actual is None:
                continue
            output.append([row.fanduel_id,family,metric,role,row.verified_outcome,forecast,actual,
                           daily,reviewed,latest.isoformat(),forecast-actual,
                           None if daily is None else daily-actual,
                           None if reviewed is None else reviewed-actual])
    return pd.DataFrame(output,columns=FIELDS)


def summarize_sources(details):
    """Report accuracy and coverage; compare DAILY and reviewed on identical rows."""
    rows = []
    for (metric,provider), group in details.groupby(['metric','provider']):
        for role, subset in [('all',group), *list(group.groupby('role'))]:
            paired = subset.dropna(subset=['daily_error','reviewed_error'])
            rows.append(dict(metric=metric,provider=provider,role=role,
                             verified_forecasts=len(subset),paired_forecasts=len(paired),
                             source_mae=subset.source_error.abs().mean(),
                             source_bias=subset.source_error.mean(),
                             source_mae_paired=paired.source_error.abs().mean(),
                             daily_mae_paired=paired.daily_error.abs().mean(),
                             reviewed_mae_paired=paired.reviewed_error.abs().mean()))
    return pd.DataFrame(rows)


def head_to_head(details):
    """Compare source pairs only where both forecast the identical player/outcome."""
    rows = []
    for metric, group in details.groupby('metric'):
        for left,right in combinations(sorted(group.provider.unique()),2):
            a = group.loc[group.provider.eq(left),['fanduel_id','source_error']]
            b = group.loc[group.provider.eq(right),['fanduel_id','source_error']]
            both = a.merge(b,on='fanduel_id',suffixes=('_a','_b'),validate='one_to_one')
            if both.empty:
                continue
            mae_a,mae_b = both.source_error_a.abs().mean(),both.source_error_b.abs().mean()
            rows.append(dict(metric=metric,provider_a=left,provider_b=right,
                             common_players=len(both),mae_a=mae_a,mae_b=mae_b,
                             mae_b_minus_a=mae_b-mae_a))
    return pd.DataFrame(rows)


def review_source_dates(replay, target_day):
    """Evaluate one independently scoped frozen contest per earlier date.

    A date with conflicting player rows or multiple contests fails closed.
    Equal-day summaries are descriptive, not training weights.
    """
    if replay.empty:
        return pd.DataFrame(columns=['slate_date', *FIELDS]), pd.DataFrame(), pd.DataFrame()
    if not {'slate_date','fanduel_id'} <= set(replay):
        raise ValueError('Dated frozen replay required.')
    days = pd.to_datetime(replay.slate_date, errors='coerce')
    target = pd.Timestamp(target_day)
    if days.isna().any() or target.tzinfo is not None or (days.dt.normalize() >= target.normalize()).any():
        raise ValueError('Source history must contain only earlier dated slates.')
    output = []
    for day, group in replay.assign(_day=days.dt.date).groupby('_day'):
        group = group.drop(columns='_day').drop_duplicates()
        contests = group.fanduel_id.astype(str).str.extract(r'^([0-9]+)-[0-9]+$', expand=False)
        if contests.isna().any() or contests.nunique() != 1:
            raise ValueError('Source history requires one verified contest per date.')
        details = review_sources(group)
        if not details.empty:
            output.append(details.assign(slate_date=day.isoformat()))
    if not output:
        return pd.DataFrame(columns=['slate_date', *FIELDS]), pd.DataFrame(), pd.DataFrame()
    details = pd.concat(output, ignore_index=True)
    daily = []
    for day, group in details.groupby('slate_date'):
        summary = summarize_sources(group)
        daily.append(summary.loc[summary.role.eq('all')].assign(slate_date=day))
    daily = pd.concat(daily, ignore_index=True)
    aggregate = []
    for (metric, provider), group in daily.groupby(['metric','provider']):
        paired = group.loc[group.paired_forecasts.gt(0)].copy()
        daily_edge = paired.daily_mae_paired - paired.source_mae_paired
        reviewed_edge = paired.reviewed_mae_paired - paired.source_mae_paired
        aggregate.append(dict(metric=metric, provider=provider,
                              dates=group.slate_date.nunique(),
                              verified_forecasts=int(group.verified_forecasts.sum()),
                              paired_dates=paired.slate_date.nunique(),
                              paired_forecasts=int(paired.paired_forecasts.sum()),
                              equal_day_mae=group.source_mae.mean(),
                              equal_day_paired_mae=paired.source_mae_paired.mean(),
                              equal_day_daily_mae=paired.daily_mae_paired.mean(),
                              equal_day_reviewed_mae=paired.reviewed_mae_paired.mean(),
                              equal_day_edge_vs_daily=daily_edge.mean(),
                              equal_day_edge_vs_reviewed=reviewed_edge.mean(),
                              days_better_than_daily=int(daily_edge.gt(0).sum()),
                              days_better_than_reviewed=int(reviewed_edge.gt(0).sum())))
    return details, daily, pd.DataFrame(aggregate)
