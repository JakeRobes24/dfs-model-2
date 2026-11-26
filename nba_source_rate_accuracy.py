"""Historical same-provider production-rate diagnostics; never modifies scoring."""
import numpy as np
import pandas as pd

from nba_source_accuracy import review_source_dates, records
from nba_distribution_review import bounded, timestamp
from slate_research import POINT_SOURCE_GROUPS

MIN_ACTUAL_MINUTES = 10.0
MIN_FORECAST_MINUTES = 10.0


def review_source_rates(replay, target_day, *, source_details=None):
    """Use only accepted, same-record point/minute forecasts on earlier dates.

    Exclude brief appearances and very small projected minutes (fixed 10-minute
    floor) to avoid unstable ratios. DNPs have no observed production rate.
    All baselines are evaluated on identical rows; this is descriptive evidence.
    """
    if source_details is None:
        source_details, _, _ = review_source_dates(replay, target_day)
    if source_details.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    keys = ['slate_date','fanduel_id','provider','observed_at']
    played = source_details.loc[source_details.outcome.eq('played')]
    points = played.loc[played.metric.eq('FD points')]
    minutes = played.loc[played.metric.eq('Minutes')]
    paired = points.merge(minutes, on=keys, suffixes=('_points','_minutes'), validate='one_to_one')
    if paired.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    archive = replay.copy()
    archive['slate_date'] = pd.to_datetime(archive.slate_date).dt.date.astype(str)
    archive = archive.drop_duplicates().set_index(['slate_date','fanduel_id'])
    result = []
    for row in paired.itertuples():
        raw = archive.loc[(row.slate_date,row.fanduel_id)]
        # A timestamp match alone cannot prove the forecasts were paired.
        exact = [note for note in records(raw.get('projection_sources_json'))
                 if POINT_SOURCE_GROUPS.get(note.get('source')) == row.provider
                 and note.get('family') == row.provider
                 and timestamp(note.get('observed_at')) == timestamp(row.observed_at)
                 and bounded(note.get('points'),0,150) == row.forecast_points
                 and bounded(note.get('paired_minutes'),0,48) == row.forecast_minutes]
        if not exact or row.actual_minutes < MIN_ACTUAL_MINUTES or row.forecast_minutes < MIN_FORECAST_MINUTES:
            continue
        actual = row.actual_points / row.actual_minutes
        source = row.forecast_points / row.forecast_minutes
        def rate(points, minutes):
            p, m = bounded(points,0,150), bounded(minutes,MIN_FORECAST_MINUTES,60)
            return None if p is None or m is None else p/m
        daily = rate(row.daily_points,row.daily_minutes)
        reviewed = rate(row.reviewed_points,row.reviewed_minutes)
        result.append(dict(slate_date=row.slate_date,fanduel_id=row.fanduel_id,provider=row.provider,
                           observed_at=row.observed_at,actual_minutes=row.actual_minutes,
                           source_minutes=row.forecast_minutes,source_fd_points=row.forecast_points,
                           daily_minutes=row.daily_minutes,daily_fd_points=row.daily_points,
                           nba_source=raw.get('nba_source'),
                           source_fppm=source,actual_fppm=actual,daily_fppm=daily,reviewed_fppm=reviewed,
                           source_error=source-actual,daily_error=None if daily is None else daily-actual,
                           reviewed_error=None if reviewed is None else reviewed-actual,
                           actual_fd_points=row.actual_points, reviewed_minutes=row.reviewed_minutes,
                           source_rate_reviewed_minutes_fd=(source*row.reviewed_minutes if reviewed is not None else None),
                           daily_rate_reviewed_minutes_fd=(daily*row.reviewed_minutes if daily is not None and reviewed is not None else None),
                           reviewed_fd=row.reviewed_points if reviewed is not None else None))
    details = pd.DataFrame(result)
    if details.empty:
        return details, pd.DataFrame(), pd.DataFrame()
    days = []
    for (day,provider), group in details.groupby(['slate_date','provider']):
        common = group.dropna(subset=['daily_error','reviewed_error'])
        days.append(dict(slate_date=day,provider=provider,forecasts=len(group),paired_forecasts=len(common),
                         source_mae=group.source_error.abs().mean(),source_bias=group.source_error.mean(),
                         source_mae_paired=common.source_error.abs().mean(),
                         daily_mae_paired=common.daily_error.abs().mean(),
                         reviewed_mae_paired=common.reviewed_error.abs().mean()))
    daily = pd.DataFrame(days)
    summary = []
    for provider, group in daily.groupby('provider'):
        common = group.loc[group.paired_forecasts.gt(0)]
        edge = common.daily_mae_paired-common.source_mae_paired
        reviewed_edge = common.reviewed_mae_paired-common.source_mae_paired
        summary.append(dict(provider=provider,dates=len(group),forecasts=int(group.forecasts.sum()),
                            paired_dates=len(common),paired_forecasts=int(common.paired_forecasts.sum()),
                            equal_day_rate_mae=group.source_mae.mean(),
                            equal_day_edge_vs_daily=edge.mean(),
                            equal_day_edge_vs_reviewed=reviewed_edge.mean(),
                            days_better_than_daily=int(edge.gt(0).sum()),
                            days_better_than_reviewed=int(reviewed_edge.gt(0).sum())))
    return details,daily,pd.DataFrame(summary)


def fixed_minutes_rate_review(details):
    """Hold reviewed minutes fixed to isolate the effect of rate substitution.

    This is an offline counterfactual, not an eligible live scoring rule.
    Restrict to identical complete paired samples and report dates separately.
    """
    if details.empty:
        return pd.DataFrame(), pd.DataFrame()
    required = ['source_rate_reviewed_minutes_fd','daily_rate_reviewed_minutes_fd',
                'reviewed_fd','actual_fd_points']
    if not {'slate_date','provider','fanduel_id',*required} <= set(details):
        raise ValueError('Complete same-provider rate diagnostics required.')
    if details.duplicated(['slate_date','provider','fanduel_id']).any():
        raise ValueError('Rate diagnostics require unique player/provider/date observations.')
    paired = details.dropna(subset=required).copy()
    if paired.empty:
        return pd.DataFrame(), pd.DataFrame()
    for label, field in [('source','source_rate_reviewed_minutes_fd'),
                         ('daily','daily_rate_reviewed_minutes_fd'),('reviewed','reviewed_fd')]:
        paired[label+'_absolute_error'] = (paired[field]-paired.actual_fd_points).abs()
    daily = paired.groupby(['slate_date','provider'],as_index=False).agg(
        paired_players=('fanduel_id','size'),
        source_rate_mae=('source_absolute_error','mean'),
        daily_rate_mae=('daily_absolute_error','mean'),
        reviewed_mae=('reviewed_absolute_error','mean'))
    daily['source_edge_vs_daily'] = daily.daily_rate_mae - daily.source_rate_mae
    daily['source_edge_vs_reviewed'] = daily.reviewed_mae - daily.source_rate_mae
    summary = daily.groupby('provider',as_index=False).agg(
        dates=('slate_date','nunique'),paired_players=('paired_players','sum'),
        equal_day_source_mae=('source_rate_mae','mean'),
        equal_day_daily_mae=('daily_rate_mae','mean'),
        equal_day_reviewed_mae=('reviewed_mae','mean'),
        equal_day_edge_vs_daily=('source_edge_vs_daily','mean'),
        equal_day_edge_vs_reviewed=('source_edge_vs_reviewed','mean'),
        days_better_than_reviewed=('source_edge_vs_reviewed',lambda s: int(s.gt(0).sum())))
    return daily, summary

def fixed_rate_shrinkage_review(details):
    """Compare fixed rate blends on identical supported rows and playing time.

    Input is the accepted same-record, earlier-date output of review_source_rates.
    No forecast weights are selected here; no changes to the live player pool.
    """
    if details.empty:
        return pd.DataFrame(), pd.DataFrame()
    keys = ['slate_date', 'provider', 'fanduel_id']
    numbers = ['reviewed_minutes', 'actual_minutes', 'reviewed_fd',
               'actual_fd_points', 'source_fppm', 'source_rate_reviewed_minutes_fd']
    if not set(keys + numbers) <= set(details):
        raise ValueError('Complete accepted paired rate details required.')
    if details[keys].isna().any().any() or details.duplicated(keys).any():
        raise ValueError('Rate shrinkage requires unique player/provider/date observations.')
    frame = details[keys + numbers].copy()
    frame[numbers] = frame[numbers].apply(pd.to_numeric, errors='coerce')
    finite = np.isfinite(frame[numbers]).all(axis=1)
    frame = frame.loc[finite & frame.reviewed_minutes.between(10, 60)
                      & frame.actual_minutes.between(10, 60)
                      & frame.reviewed_fd.gt(0)
                      & frame.source_fppm.gt(0) & frame.source_fppm.le(5)].copy()
    if frame.empty:
        return pd.DataFrame(), pd.DataFrame()
    consistent = np.isclose(frame.source_rate_reviewed_minutes_fd,
                            frame.source_fppm * frame.reviewed_minutes,
                            rtol=0, atol=1e-6)
    if not consistent.all():
        raise ValueError('Same-provider rate and fixed-minutes points disagree.')
    base_rate = frame.reviewed_fd / frame.reviewed_minutes
    observed_rate = frame.actual_fd_points / frame.actual_minutes
    frame = frame.assign(base_rate=base_rate, observed_rate=observed_rate)
    rows = []
    for (day, provider), g in frame.groupby(['slate_date', 'provider']):
        for weight in (0., .2, .4, 1.):
            rate = (1-weight)*g.base_rate + weight*g.source_fppm
            err = rate*g.reviewed_minutes-g.actual_fd_points
            rate_err = rate-g.observed_rate
            rows.append(dict(slate_date=day, provider=provider, independent_weight=weight,
                             paired_players=len(g), fd_mae=err.abs().mean(), fd_bias=err.mean(),
                             fppm_mae=rate_err.abs().mean(), fppm_bias=rate_err.mean()))
    daily = pd.DataFrame(rows)
    baseline = daily.loc[daily.independent_weight.eq(0),
                         ['slate_date', 'provider', 'fd_mae']].rename(columns={'fd_mae':'baseline_mae'})
    daily = daily.merge(baseline, on=['slate_date', 'provider'], validate='many_to_one')
    daily['fd_edge_vs_reviewed'] = daily.baseline_mae-daily.fd_mae
    summary = daily.groupby(['provider','independent_weight'],as_index=False).agg(
        dates=('slate_date','nunique'), paired_players=('paired_players','sum'),
        equal_day_fd_mae=('fd_mae','mean'), equal_day_fd_bias=('fd_bias','mean'),
        equal_day_fppm_mae=('fppm_mae','mean'),
        equal_day_fd_edge=('fd_edge_vs_reviewed','mean'),
        improved_dates=('fd_edge_vs_reviewed',lambda s: int(s.gt(1e-9).sum())))
    return daily, summary


def paired_rate_attribution(details):
    """Compare swapping minutes, production rate, or both on identical played rows."""
    if details.empty:
        return pd.DataFrame(), pd.DataFrame()
    keys = ['slate_date', 'provider', 'fanduel_id']
    numbers = ['actual_minutes', 'actual_fd_points', 'daily_minutes', 'daily_fd_points',
               'reviewed_minutes', 'reviewed_fd', 'source_minutes', 'source_fd_points', 'source_fppm']
    provenance = 'nba_source'
    if not set(keys + numbers + [provenance]) <= set(details):
        raise ValueError('Use dated paired forecasts with official outcome provenance.')
    if details[keys].isna().any().any() or details.duplicated(keys).any():
        raise ValueError('Use one row per source, player and date.')
    data = details[keys + numbers + [provenance]].copy()
    data[numbers] = data[numbers].apply(pd.to_numeric, errors='coerce')
    minutes = ['actual_minutes', 'daily_minutes', 'reviewed_minutes', 'source_minutes']
    forecasts = ['daily_fd_points', 'reviewed_fd', 'source_fd_points']
    valid = np.isfinite(data[numbers]).all(axis=1)
    valid &= data[provenance].fillna('').astype(str).str.strip().ne('')
    valid &= data[minutes].ge(MIN_ACTUAL_MINUTES).all(axis=1) & data[minutes].le(60).all(axis=1)
    valid &= data.source_minutes.le(48) & data[forecasts].gt(0).all(axis=1)
    data = data.loc[valid]
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()
    if not np.isclose(data.source_fppm * data.source_minutes, data.source_fd_points,
                      rtol=0, atol=1e-6).all():
        raise ValueError('Source minutes and rate do not reproduce source points.')

    rows = []
    for (day, provider), group in data.groupby(['slate_date', 'provider']):
        reviewed_rate = group.reviewed_fd / group.reviewed_minutes
        actual_rate = group.actual_fd_points / group.actual_minutes
        policies = [
            ('DAILY', group.daily_minutes, group.daily_fd_points / group.daily_minutes),
            ('Reviewed', group.reviewed_minutes, reviewed_rate),
            ('Provider minutes only', group.source_minutes, reviewed_rate),
            ('Provider scoring rate only', group.reviewed_minutes, group.source_fppm),
            ('Provider minutes and rate', group.source_minutes, group.source_fppm),
        ]
        baseline_error = (group.reviewed_fd - group.actual_fd_points).abs()
        for policy, time, rate in policies:
            fd_error = time * rate - group.actual_fd_points
            rate_error = rate - actual_rate
            edge = baseline_error - fd_error.abs()
            rows.append(dict(slate_date=day, provider=provider, policy=policy,
                             paired_players=len(group), minutes_mae=(time-group.actual_minutes).abs().mean(),
                             fppm_mae=rate_error.abs().mean(), fppm_bias=rate_error.mean(),
                             fd_mae=fd_error.abs().mean(), fd_bias=fd_error.mean(),
                             fd_edge_vs_reviewed=edge.mean(),
                             players_improved=int(edge.gt(1e-9).sum()),
                             players_worsened=int(edge.lt(-1e-9).sum())))
    daily = pd.DataFrame(rows)
    summary = daily.groupby(['provider', 'policy'], sort=False, as_index=False).agg(
        dates=('slate_date', 'nunique'), paired_players=('paired_players', 'sum'),
        equal_day_minutes_mae=('minutes_mae', 'mean'), equal_day_fppm_mae=('fppm_mae', 'mean'),
        equal_day_fppm_bias=('fppm_bias', 'mean'), equal_day_fd_mae=('fd_mae', 'mean'),
        equal_day_fd_bias=('fd_bias', 'mean'), equal_day_fd_edge=('fd_edge_vs_reviewed', 'mean'),
        improving_dates=('fd_edge_vs_reviewed', lambda s: int(s.gt(1e-9).sum())))
    return daily, summary
