"""Historical same-provider production-rate diagnostics; never modifies scoring."""
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
                           source_fppm=source,actual_fppm=actual,daily_fppm=daily,reviewed_fppm=reviewed,
                           source_error=source-actual,daily_error=None if daily is None else daily-actual,
                           reviewed_error=None if reviewed is None else reviewed-actual))
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
