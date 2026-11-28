"""Matched historical opportunity scoring rank diagnostics, not lineup selection."""
from itertools import combinations
import numpy as np
import pandas as pd

KEYS=['date','week','game_id','team','gsis_id','position','channel']
BASE='Actual scoring average'
EXPECTED='Expected scoring average'
BLEND='Equal actual and expected blend'


def matched_forecasts(frame):
    required=set(KEYS+['policy','actual','forecast'])
    if not required<=set(frame) or frame[KEYS].isna().any().any() or frame.duplicated(KEYS+['policy']).any():
        raise ValueError('Unique exact player-game-channel-policy rows required')
    if set(frame.policy)!={BASE,EXPECTED,BLEND} or not np.isfinite(frame[['actual','forecast']].to_numpy(dtype=float)).all():
        raise ValueError('Require three finite archived policies')
    if frame.groupby(KEYS).actual.nunique().ne(1).any():
        raise ValueError('Outcome disagreement')
    wide=frame.pivot(index=KEYS,columns='policy',values='forecast')
    if wide.isna().any().any() or not np.allclose(wide[BLEND],(wide[BASE]+wide[EXPECTED])/2,atol=1e-8,rtol=0):
        raise ValueError('Incomplete paired forecasts or blend disagreement')
    wide['actual']=frame.groupby(KEYS).actual.first()
    return wide.reset_index()


def compare_rank_groups(frame, *, scope):
    """Fixed prior-chosen blend vs raw historical scoring, same played cohort."""
    if scope not in ('team','game'):
        raise ValueError('Unknown group scope')
    x=matched_forecasts(frame)
    if not x.channel.isin(['receiving','rushing']).all():
        raise ValueError('Unsupported channel')
    weight=x.channel.map({'receiving':.75,'rushing':1.})
    x['fixed_prior_blend']=(1-weight)*x[BASE]+weight*x[EXPECTED]
    fields=['date','week','game_id','position','channel']+(['team'] if scope=='team' else [])
    rows=[]
    for k,g in x.groupby(fields,sort=True):
        if len(g)<2:continue
        y=g.actual.to_numpy(); best=y.max()
        for policy in (BASE,EXPECTED,'fixed_prior_blend'):
            p=g[policy].to_numpy(); leaders=np.flatnonzero(np.isclose(p,p.max(),atol=1e-9,rtol=0))
            # Average over tied forecast leaders; no outcome-dependent tie break.
            correct=[]
            for i,j in combinations(range(len(g)),2):
                dy=y[i]-y[j];dp=p[i]-p[j]
                if abs(dy)<=1e-9:continue
                correct.append(.5 if abs(dp)<=1e-9 else float(dy*dp>0))
            rows.append(dict(zip(fields,k),policy=policy,players=len(g),pairs=len(correct),
                order_accuracy=float(np.mean(correct)) if correct else np.nan,
                leader_regret=float(best-y[leaders].mean()),
                leader_hit=float(np.isclose(y[leaders],best,atol=1e-9,rtol=0).mean())))
    return pd.DataFrame(rows)


def summarize(rows):
    cols=['order_accuracy','leader_regret','leader_hit']
    weekly=rows.groupby(['channel','position','policy','week'])[cols].mean()
    s=weekly.groupby(level=[0,1,2]).mean().reset_index()
    counts=rows.groupby(['channel','position','policy']).agg(groups=('players','size'),pairs=('pairs','sum'),weeks=('week','nunique')).reset_index()
    return s.merge(counts,validate='one_to_one')
