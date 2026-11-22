"""Paired post-slate assessment of frozen DAILY and adjusted projections."""
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    'fanduel_id', 'eligible', 'verified_outcome', 'daily_minutes',
    'adjusted_minutes', 'actual_minutes', 'daily_points', 'adjusted_fd_points',
    'actual_points',
}


def compare_frozen_projections(replay):
    """Score both projections on identical player rows with verified outcomes."""
    if not REQUIRED_COLUMNS <= set(replay) or not replay.fanduel_id.is_unique:
        raise ValueError('Use one frozen replay with unique FanDuel player IDs.')
    eligible = replay.loc[replay.eligible.eq(True)].copy()
    played = eligible.verified_outcome.eq('played')
    did_not_play = eligible.verified_outcome.eq('did_not_play')
    rows = []
    for metric, baseline, adjusted, outcome, scope in [
        ('FanDuel points', 'daily_points', 'adjusted_fd_points', 'actual_points', played | did_not_play),
        ('Minutes', 'daily_minutes', 'adjusted_minutes', 'actual_minutes', played),
    ]:
        values = eligible[[baseline, adjusted, outcome]].apply(pd.to_numeric, errors='coerce')
        values = values.replace([np.inf, -np.inf], np.nan).loc[scope].copy()
        if metric == 'FanDuel points':
            values.loc[did_not_play.reindex(values.index), outcome] = 0
        values = values.dropna()
        changed = (values[adjusted] - values[baseline]).abs().gt(.01)
        for group, sample in [('All paired players', values), ('Changed projections', values.loc[changed])]:
            daily_error = sample[baseline] - sample[outcome]
            adjusted_error = sample[adjusted] - sample[outcome]
            daily_mae, adjusted_mae = daily_error.abs().mean(), adjusted_error.abs().mean()
            rows.append({
                'Metric': metric, 'Sample': group, 'Paired players': len(sample),
                'Eligible with verified outcome': int(scope.sum()),
                'DAILY MAE': daily_mae, 'Adjusted MAE': adjusted_mae,
                'MAE improvement': daily_mae - adjusted_mae,
                'DAILY bias': daily_error.mean(), 'Adjusted bias': adjusted_error.mean(),
            })
    return pd.DataFrame(rows)
