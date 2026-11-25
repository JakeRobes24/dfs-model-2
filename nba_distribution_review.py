"""Post-slate validation of archived PropSims uncertainty forecasts.

Provider quantiles and participation probabilities are distinct from live scoring.
Only verified outcomes and fresh, frozen pre-tip forecasts are evaluated.
"""
import json
import math

import pandas as pd

SOURCE = 'https://propsims.com/nba/dfs/'
COLUMNS = [
    'fanduel_id', 'published_utc', 'outcome', 'played', 'actual_points',
    'fd_median', 'median_absolute_error', 'daily_absolute_error', 'reviewed_absolute_error',
    'fd_p10', 'fd_p85', 'below_p10', 'above_p85', 'inside_interval',
    'p10_pinball', 'p85_pinball', 'play_probability', 'play_brier',
    'conditional_fd_median', 'conditional_absolute_error',
]


def bounded(value, low, high):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if math.isfinite(value) and low <= value <= high else None


def timestamp(value):
    try:
        stamp = pd.Timestamp(value)
        if pd.notna(stamp) and stamp.tzinfo is not None:
            return stamp.tz_convert('UTC')
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def review_distribution(replay):
    """A verified DNP is zero for unconditional outcomes only; unknowns are excluded."""
    if 'propsims_distribution_json' not in replay:
        return pd.DataFrame(columns=COLUMNS)
    required = {'fanduel_id', 'eligible', 'verified_outcome', 'actual_points',
                'daily_points', 'adjusted_fd_points', 'replay_captured_at_utc',
                'replay_cutoff_utc', 'replay_before_full_slate_tip', 'replay_timing'}
    if not required <= set(replay) or not replay.fanduel_id.is_unique or replay.fanduel_id.isna().any():
        raise ValueError('Distribution evaluation requires a unique frozen player replay.')
    records = []
    for row in replay.itertuples():
        if (str(row.eligible).lower() != 'true'
                or str(row.replay_before_full_slate_tip).lower() != 'true'
                or row.replay_timing != 'before_scheduled_tip'
                or row.verified_outcome not in ('played', 'did_not_play')):
            continue
        capture, cutoff = timestamp(row.replay_captured_at_utc), timestamp(row.replay_cutoff_utc)
        if capture is None or cutoff is None or capture >= cutoff:
            continue
        try:
            entries = json.loads(row.propsims_distribution_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            continue
        estimate = entries[0]
        published = timestamp(estimate.get('observed_at'))
        median = bounded(estimate.get('fd_median'), 0, 150)
        if (estimate.get('source') != SOURCE or published is None or median is None
                or not capture - pd.Timedelta(hours=6) <= published <= capture):
            continue
        played = row.verified_outcome == 'played'
        actual = bounded(row.actual_points, -150, 300) if played else 0.0
        if actual is None:
            continue
        daily = bounded(row.daily_points, 0, 150)
        reviewed = bounded(row.adjusted_fd_points, 0, 150)
        lower = bounded(estimate.get('fd_p10'), 0, 150)
        upper = bounded(estimate.get('fd_p85'), 0, 150)
        if lower is None or upper is None or not lower <= median <= upper:
            lower = upper = None
        probability = bounded(estimate.get('play_probability'), 0, 1)
        conditional = bounded(estimate.get('conditional_fd_median'), 0, 150)
        def pinball(pred, quantile):
            if pred is None:
                return None
            diff = actual - pred
            return max(quantile * diff, (quantile - 1) * diff)
        records.append(dict(
            fanduel_id=row.fanduel_id, published_utc=published.isoformat(),
            outcome=row.verified_outcome, played=played, actual_points=actual,
            fd_median=median, median_absolute_error=abs(median-actual),
            daily_absolute_error=abs(daily-actual) if daily is not None else None,
            reviewed_absolute_error=abs(reviewed-actual) if reviewed is not None else None,
            fd_p10=lower, fd_p85=upper,
            below_p10=actual < lower if lower is not None else None,
            above_p85=actual > upper if upper is not None else None,
            inside_interval=lower <= actual <= upper if lower is not None else None,
            p10_pinball=pinball(lower, .10), p85_pinball=pinball(upper, .85),
            play_probability=probability,
            play_brier=(probability-int(played))**2 if probability is not None else None,
            conditional_fd_median=conditional,
            conditional_absolute_error=abs(conditional-actual) if played and conditional is not None else None,
        ))
    return pd.DataFrame(records, columns=COLUMNS)


def summarize_distribution(details):
    """Matched-sample errors, interval diagnostics and Brier score; no promotion."""
    if details.empty:
        return pd.DataFrame()
    paired = details.dropna(subset=['daily_absolute_error','reviewed_absolute_error','median_absolute_error'])
    interval = details.dropna(subset=['fd_p10','fd_p85'])
    availability = details.dropna(subset=['play_probability'])
    conditional = details.dropna(subset=['conditional_absolute_error'])
    def average(frame, field):
        return float(frame[field].mean()) if len(frame) else None
    return pd.DataFrame([{
        'verified_forecasts': len(details),
        'played': int(details.played.sum()), 'verified_dnp': int((~details.played).sum()),
        'paired_points_count': len(paired),
        'daily_mae_paired': average(paired,'daily_absolute_error'),
        'reviewed_mae_paired': average(paired,'reviewed_absolute_error'),
        'propsims_median_mae_paired': average(paired,'median_absolute_error'),
        'interval_count': len(interval),
        'below_p10_rate': average(interval,'below_p10'),
        'above_p85_rate': average(interval,'above_p85'),
        'inclusive_interval_rate': average(interval,'inside_interval'),
        'p10_pinball': average(interval,'p10_pinball'),
        'p85_pinball': average(interval,'p85_pinball'),
        'availability_count': len(availability),
        'mean_play_probability': average(availability,'play_probability'),
        'observed_play_rate': average(availability,'played'),
        'play_brier': average(availability,'play_brier'),
        'conditional_played_count': len(conditional),
        'conditional_mae_played': average(conditional,'conditional_absolute_error'),
    }])
