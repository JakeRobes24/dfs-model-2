"""Offline dependence diagnostics, retaining each player's empirical marginal."""
from itertools import combinations
import numpy as np
import pandas as pd


def reorder_draws(draws, normal_scores, teams, games, *, same, opposite, weight=1.):
    """Rank-couple fixed columns; shared player draws remain shared across rosters."""
    x, z = np.asarray(draws, dtype=float), np.asarray(normal_scores, dtype=float)
    if (x.ndim != 2 or x.shape != z.shape or not x.size
            or not np.isfinite(x).all() or not np.isfinite(z).all()
            or len(teams) != x.shape[1] or len(games) != x.shape[1]
            or not all(teams) or not all(games)
            or not np.isfinite([same, opposite, weight]).all()
            or not -1 <= same <= 1 or not -1 <= opposite <= 1 or not 0 <= weight <= 1):
        raise ValueError('Invalid fixed draw or dependence input')
    corr = np.eye(x.shape[1])
    for i, j in combinations(range(x.shape[1]), 2):
        if games[i] == games[j]:
            corr[i,j] = corr[j,i] = weight*(same if teams[i] == teams[j] else opposite)
    minimum = float(np.linalg.eigvalsh(corr)[0])
    if minimum < .01:
        corr = np.eye(len(corr))+(corr-np.eye(len(corr)))*(.99/(1-minimum))
    ranks = z@np.linalg.cholesky(corr).T
    out = np.empty_like(x)
    for j in range(x.shape[1]):
        out[np.argsort(ranks[:,j],kind='stable'),j] = np.sort(x[:,j])
    return out, minimum


def weekly_dependence_stability(frame):
    """Descriptive paired weekly score stability, not a new training/test split."""
    keys = ['pair','week']
    metrics = ['pairs','crps','interval_score','coverage']
    labels = ['Independent','Frozen role dependence']
    if (frame.duplicated(keys+['policy']).any() or frame[keys].isna().any().any()
            or set(frame.policy) != set(labels)
            or not np.isfinite(frame[metrics].to_numpy(dtype=float)).all()):
        raise ValueError('Require finite unique paired weekly evidence')
    wide = frame.pivot(index=keys,columns='policy',values=metrics)
    a,b = (wide.xs(p,axis=1,level=1) for p in labels)
    if wide.isna().any().any() or not a.pairs.eq(b.pairs).all() or not a.pairs.gt(0).all():
        raise ValueError('Mismatched weekly support')
    delta = a-b
    out = []
    for pair,g in delta.groupby(level=0):
        v = g.crps
        loo = [v.drop(i).mean() for i in v.index] if len(v)>1 else []
        out.append(dict(pair=pair,weeks=len(g),pairs=int(a.loc[pair].pairs.sum()),
                        mean_crps_gain=float(v.mean()),crps_win_weeks=int(v.gt(0).sum()),
                        leave_one_week_min=float(min(loo)) if loo else None,
                        leave_one_week_max=float(max(loo)) if loo else None,
                        mean_interval_gain=float(g.interval_score.mean()),
                        interval_win_weeks=int(g.interval_score.gt(0).sum())))
    return out
