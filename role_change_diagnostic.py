"""Offline role-change diagnostics; no live forecast adjustments."""
from math import ceil
import numpy as np
import pandas as pd


def role_range_comparison(train, test, *, period, actual, forecast, min_group=30):
    """Fit pooled and role-conditional symmetric 80% absolute-error radii.

    Earlier training only; input role flags must be made without target
    outcomes. This is a conditional played-sample diagnostic, not a full
    simulation, probability of availability, or promotion decision.
    """
    if type(min_group) is not int or min_group < 1:
        raise ValueError("Invalid minimum group")
    if train.empty or test.empty or train[period].isna().any() or test[period].isna().any():
        raise ValueError("Complete training and evaluation periods required")
    if train[period].max() >= test[period].min():
        raise ValueError("Training must strictly precede evaluation")
    for frame in (train,test):
        if not frame.trigger.map(lambda x: isinstance(x,(bool,np.bool_))).all():
            raise ValueError("Explicit pre-outcome boolean role flags required")
        if not np.isfinite(frame[[actual,forecast]].to_numpy(dtype=float)).all():
            raise ValueError("Finite paired forecasts and outcomes required")
    err=(train[actual]-train[forecast]).abs()
    def radius(values):
        x=np.sort(values)
        return float(x[min(len(x)-1,ceil(.8*(len(x)+1))-1)])
    pooled=radius(err)
    radii={b:radius(err[train.trigger.eq(b)]) if train.trigger.eq(b).sum()>=min_group else pooled
           for b in (True,False)}
    eval_err=(test[actual]-test[forecast]).abs().to_numpy()
    scores={}
    for name,r in [('pooled',np.full(len(test),pooled)),
                   ('role',test.trigger.map(radii).to_numpy())]:
        scored=test.assign(coverage=eval_err<=r,width=2*r,score=2*r+10*np.maximum(0,eval_err-r))
        scores[name]={k:float(v) for k,v in scored.groupby(period)[['coverage','width','score']].mean().mean().items()}
    return dict(pooled_radius=pooled,role_radii=radii,training=len(train),evaluation=len(test),scores=scores)
