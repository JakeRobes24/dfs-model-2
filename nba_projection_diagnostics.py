"""Post-slate only: exact decomposition of frozen NBA FanDuel point forecast errors.

This module never updates pre-lock projections or model weights.
"""
import numpy as np
import pandas as pd

REQUIRED = ('fanduel_id', 'eligible', 'verified_outcome', 'daily_minutes',
            'adjusted_minutes', 'actual_minutes', 'daily_points',
            'adjusted_fd_points', 'actual_points')


def decompose_played_errors(replay):
    """Separate minutes and per-minute contributions; not causal attribution."""
    if not set(REQUIRED).issubset(replay.columns):
        raise ValueError('Missing frozen replay columns')
    if replay.fanduel_id.isna().any() or not replay.fanduel_id.is_unique:
        raise ValueError('Replay must contain unique, nonmissing FanDuel IDs')
    played = replay.loc[replay.eligible.eq(True) & replay.verified_outcome.eq('played')].copy()
    numeric = list(REQUIRED[3:])
    for column in numeric:
        played[column] = pd.to_numeric(played[column], errors='coerce')
    played[numeric] = played[numeric].replace([np.inf, -np.inf], np.nan)
    played = played.dropna(subset=numeric)
    played = played.loc[(played[['daily_minutes', 'adjusted_minutes', 'actual_minutes']] > 0).all(axis=1)]
    played = played.loc[(played[['daily_points', 'adjusted_fd_points', 'actual_points']] >= 0).all(axis=1)]
    rows = []
    for label, minutes_col, points_col in (
        ('DAILY', 'daily_minutes', 'daily_points'),
        ('Adjusted', 'adjusted_minutes', 'adjusted_fd_points'),
    ):
        predicted_rate = played[points_col] / played[minutes_col]
        actual_rate = played.actual_points / played.actual_minutes
        minute_error = (played[minutes_col] - played.actual_minutes) * predicted_rate
        rate_error = played.actual_minutes * (predicted_rate - actual_rate)
        miss = played[points_col] - played.actual_points
        if not np.allclose(minute_error + rate_error, miss, atol=1e-8):
            raise ValueError('Error decomposition identity failed')
        rows.append(pd.DataFrame({
            'fanduel_id': played.fanduel_id.to_numpy(), 'forecast': label,
            'predicted_minutes': played[minutes_col].to_numpy(),
            'actual_minutes': played.actual_minutes.to_numpy(),
            'predicted_fd_per_minute': predicted_rate.to_numpy(),
            'actual_fd_per_minute': actual_rate.to_numpy(),
            'minutes_contribution': minute_error.to_numpy(),
            'rate_contribution': rate_error.to_numpy(),
            'point_error': miss.to_numpy(),
        }))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def summarize_decomposition(details):
    """Report diagnostic absolute contributions, never optimized model weights."""
    columns = ['forecast', 'players', 'point_mae',
               'mean_abs_minutes_contribution', 'mean_abs_rate_contribution']
    if details.empty:
        return pd.DataFrame(columns=columns)
    return details.groupby('forecast', sort=True).agg(
        players=('fanduel_id', 'size'),
        point_mae=('point_error', lambda s: s.abs().mean()),
        mean_abs_minutes_contribution=('minutes_contribution', lambda s: s.abs().mean()),
        mean_abs_rate_contribution=('rate_contribution', lambda s: s.abs().mean()),
    ).reset_index()
