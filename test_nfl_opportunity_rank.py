import pandas as pd
import pytest
from nfl_opportunity_rank import *

def test_ties_and_same_sample():
    rows=[]
    for pid,a,b,e in [('a',8,3,7),('b',2,3,2)]:
        for p,v in [(BASE,b),(EXPECTED,e),(BLEND,(b+e)/2)]:
            rows.append(dict(date='2026-11-01',week=8,game_id='g',team='A',gsis_id=pid,position='WR',channel='receiving',policy=p,actual=a,forecast=v))
    f=pd.DataFrame(rows)
    r=compare_rank_groups(f,scope='team').set_index('policy')
    assert r.loc[BASE,'leader_regret']==3
    assert r.loc[BASE,'order_accuracy']==.5
    assert r.loc['fixed_prior_blend','leader_regret']==0
    with pytest.raises(ValueError):matched_forecasts(f.iloc[:-1])
    with pytest.raises(ValueError):matched_forecasts(pd.concat([f,f.iloc[:1]]))
    with pytest.raises(ValueError):matched_forecasts(f.assign(actual=[8,8,7,2,2,2]))
