import numpy as np
import pandas as pd
import pytest
from dependence_diagnostics import reorder_draws, weekly_dependence_stability


def test_preserve_marginals_and_repair_matrix():
    rng=np.random.default_rng(7)
    x=rng.normal(size=(1000,4));z=rng.normal(size=x.shape)
    y,e=reorder_draws(x,z,['A','A','B','C'],['A@B','A@B','A@B','C@D'],same=-.95,opposite=.95)
    assert e<.01
    assert np.array_equal(np.sort(x,axis=0),np.sort(y,axis=0))
    assert np.allclose(x.mean(axis=0),y.mean(axis=0))
    with pytest.raises(ValueError):
        reorder_draws(x,z[:5],['A']*4,['A@B']*4,same=0,opposite=0)


def test_weekly_common_support_and_leave_one_out():
    f=pd.DataFrame([dict(pair='QB-WR',week=w,policy=p,pairs=2,crps=v,interval_score=v,coverage=.8)
                    for w in (1,2,3) for p,v in [('Independent',5),('Frozen role dependence',4 if w!=3 else 6)]])
    d=weekly_dependence_stability(f)[0]
    assert d['pairs']==6 and d['crps_win_weeks']==2
    assert d['mean_crps_gain']==pytest.approx(1/3)
    assert d['leave_one_week_min']==0 and d['leave_one_week_max']==1
    with pytest.raises(ValueError):weekly_dependence_stability(f.iloc[:-1])
