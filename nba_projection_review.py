"""Paired post-slate assessment of frozen DAILY and adjusted projections."""
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    'fanduel_id', 'eligible', 'verified_outcome', 'daily_minutes',
    'adjusted_minutes', 'actual_minutes', 'daily_points', 'adjusted_fd_points',
    'actual_points',
}
METHOD_COLUMNS = ('minutes_method', 'projection_method')


def _paired_samples(replay):
    if not REQUIRED_COLUMNS <= set(replay) or not replay.fanduel_id.is_unique:
        raise ValueError('Use one frozen replay with unique FanDuel player IDs.')
    eligible = replay.loc[replay.eligible.eq(True)]
    played = eligible.verified_outcome.eq('played')
    did_not_play = eligible.verified_outcome.eq('did_not_play')
    for metric, baseline, adjusted, outcome, scope in [
        ('FanDuel points', 'daily_points', 'adjusted_fd_points', 'actual_points', played | did_not_play),
        ('Minutes', 'daily_minutes', 'adjusted_minutes', 'actual_minutes', played),
    ]:
        values = eligible.loc[scope, [baseline, adjusted, outcome]].apply(pd.to_numeric, errors='coerce')
        values = values.replace([np.inf, -np.inf], np.nan)
        if metric == 'FanDuel points':
            values.loc[did_not_play.reindex(values.index), outcome] = 0
        values = values.dropna()
        sample = pd.DataFrame({
            'daily_error': values[baseline] - values[outcome],
            'adjusted_error': values[adjusted] - values[outcome],
            'changed': (values[adjusted] - values[baseline]).abs().gt(.01),
        })
        yield metric, sample, int(scope.sum())


def _metrics(sample):
    daily_mae = sample.daily_error.abs().mean()
    adjusted_mae = sample.adjusted_error.abs().mean()
    return {
        'Paired players': len(sample),
        'DAILY MAE': daily_mae, 'Adjusted MAE': adjusted_mae,
        'MAE improvement': daily_mae - adjusted_mae,
        'DAILY bias': sample.daily_error.mean(), 'Adjusted bias': sample.adjusted_error.mean(),
    }


def compare_frozen_projections(replay):
    """Score both projections on identical player rows with verified outcomes."""
    rows = []
    for metric, sample, available in _paired_samples(replay):
        for group, paired in [('All paired players', sample), ('Changed projections', sample.loc[sample.changed])]:
            rows.append({'Metric': metric, 'Sample': group, 'Eligible with verified outcome': available,
                         **_metrics(paired)})
    return pd.DataFrame(rows)


def compare_adjustment_methods(replay):
    """Report paired errors for changed projections by their recorded methods."""
    if not set(METHOD_COLUMNS) <= set(replay):
        return pd.DataFrame()
    replay = replay.reset_index(drop=True)
    methods = replay[list(METHOD_COLUMNS)].fillna('').replace('', 'Unrecorded')
    rows = []
    for metric, sample, _ in _paired_samples(replay):
        changed = sample.loc[sample.changed].join(methods)
        for (minutes, points), paired in changed.groupby(list(METHOD_COLUMNS), sort=True):
            rows.append({'Metric': metric, 'Minutes method': minutes, 'Points method': points, **_metrics(paired)})
    return pd.DataFrame(rows)
