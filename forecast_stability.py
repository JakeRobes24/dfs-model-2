"""Retrospective paired forecast diagnostics; no policy selection or promotion."""
import numpy as np
import pandas as pd


def nba_error_cohorts(frame):
    fields = ['actual', 'base', 'both', 'exposure', 'base_minutes']
    keys = ['date', 'id']
    if not set(keys + fields + ['history_end']) <= set(frame):
        raise ValueError('Missing archived fields')
    x = frame.copy()
    x[fields] = x[fields].apply(pd.to_numeric, errors='raise')
    dates = pd.to_datetime(x.date, errors='raise')
    hist = pd.to_datetime(x.history_end, errors='raise')
    if (x[keys].isna().any().any() or x.duplicated(keys).any()
            or not np.isfinite(x[fields]).all().all() or not (hist < dates).all()
            or not (x.exposure.ge(0) & x.exposure.mod(1).eq(0)).all()):
        raise ValueError('Invalid paired history')
    masks = {'all': x.exposure.ge(0), 'unselected': x.exposure.eq(0),
             'selected': x.exposure.gt(0), 'repeat3plus': x.exposure.ge(3),
             'high_minutes30plus': x.base_minutes.ge(30), 'under30': x.base_minutes.lt(30)}
    rows = []
    for label, mask in masks.items():
        g = x.loc[mask]
        for period, z in [('pooled', g), *g.groupby('date')]:
            if z.empty:
                continue
            a, b = z.base-z.actual, z.both-z.actual
            delta = b.abs()-a.abs()
            rows.append(dict(cohort=label, period=period, n=len(z), base_mae=a.abs().mean(),
                             challenger_mae=b.abs().mean(), base_bias=a.mean(), challenger_bias=b.mean(),
                             improved=int((delta < -1e-8).sum()), worsened=int((delta > 1e-8).sum()),
                             base_large_miss=int((a.abs() >= 15).sum()),
                             challenger_large_miss=int((b.abs() >= 15).sum())))
    return pd.DataFrame(rows)


def nfl_week_stability(frame, *, scope):
    """Positive delta means better, including for regret. LOO is sensitivity, not CI."""
    if scope not in ('team', 'game'):
        raise ValueError('Unknown scope')
    keys = ['date', 'week', 'game_id', 'position', 'channel'] + (['team'] if scope == 'team' else [])
    metrics = ['order_accuracy', 'leader_regret', 'leader_hit']
    policies = ['Actual scoring average', 'Expected scoring average', 'fixed_prior_blend']
    fields = ['players', 'pairs'] + metrics
    if not set(keys + ['policy'] + fields) <= set(frame):
        raise ValueError('Missing archived rank fields')
    x = frame.copy()
    x[fields] = x[fields].apply(pd.to_numeric, errors='raise')
    if (x[keys].isna().any().any() or x.duplicated(keys+['policy']).any()
            or set(x.policy) != set(policies) or x.groupby(keys).policy.nunique().ne(3).any()
            or x.groupby(keys)[['players', 'pairs']].nunique().ne(1).any().any()
            or not np.isfinite(x[['players', 'pairs', 'leader_regret', 'leader_hit']]).all().all()
            or (x.players < 2).any() or (x.pairs < 0).any()
            or not x.leader_hit.between(0, 1).all() or (x.leader_regret < 0).any()
            or not x.order_accuracy.isna().eq(x.pairs.eq(0)).all()
            or not x.order_accuracy.dropna().between(0, 1).all()):
        raise ValueError('Incomplete or inconsistent paired rank groups')
    wide = x.pivot(index=keys, columns='policy', values=metrics)
    rows = []
    for metric in metrics:
        delta = (wide[metric]['fixed_prior_blend']-wide[metric][policies[0]]) * (-1 if metric == 'leader_regret' else 1)
        weekly = delta.groupby(level=['position', 'channel', 'week']).mean().dropna()
        for (position, channel), series in weekly.groupby(level=['position', 'channel']):
            values = series.to_numpy()
            loo = (values.sum()-values)/(len(values)-1) if len(values)>1 else np.array([np.nan])
            rows.append(dict(scope=scope, position=position, channel=channel, metric=metric,
                             weeks=len(values), improved=int((values>1e-9).sum()),
                             worsened=int((values< -1e-9).sum()), tied=int((abs(values)<=1e-9).sum()),
                             mean_delta=values.mean(), loo_min=loo.min(), loo_max=loo.max()))
    return pd.DataFrame(rows)
