"""Controlled tests for explicitly reviewed conditional forecasts."""
import pandas as pd
import pytest
from nba_injury_scenario_inputs import reviewed_impact_pool
from nba_injury_contingency import prepare_contingencies
from test_nba_injury_contingency import fixture

AS_OF='2026-11-23T23:00:00Z'
def inputs():
    p,b=fixture()
    p['team']=['CHA','CHA','BOS','NYK','BOS','NYK','BOS','NYK','CHA','NYK','CHA','BOS']
    e=pd.DataFrame([dict(out_ids='0',fanduel_id='10',source='reviewed conditional fixture',
                         observed_at='2026-11-23T22:55:00Z',minutes=36,fd_points=60)])
    return p,b,e

def test_reviewed_impact_is_conditional_only():
    p,b,e=inputs()
    changed,accepted=reviewed_impact_pool(p,['0'],e,AS_OF)
    assert len(accepted)==1
    assert not changed.loc[changed.fanduel_id.eq('0'),'eligible'].iat[0]
    assert changed.loc[changed.fanduel_id.eq('10'),'adjusted_fd_points'].iat[0]==60
    assert p.loc[p.fanduel_id.eq('10'),'adjusted_fd_points'].iat[0]==30
    report=prepare_contingencies(p,b,time_budget_seconds=15,conditional_evidence=e,as_of=AS_OF)
    case=report['scenarios'][0]
    assert case['impact_evidence_count']==1
    assert '10' in case['candidates'].fanduel_id.tolist()
    pd.testing.assert_frame_equal(report['baseline'],b)

@pytest.mark.parametrize('field,value',[('observed_at','2026-11-23T23:01:00Z'),
    ('observed_at','2026-11-23T12:00:00Z'),('observed_at','2026-11-23 22:55'),
    ('fanduel_id','11'),('fanduel_id','0'),('minutes',49),('fd_points',float('nan')),('source','')])
def test_unusable_evidence_rejected(field,value):
    p,b,e=inputs()
    e.loc[0,field]=value
    with pytest.raises(ValueError):
        reviewed_impact_pool(p,['0'],e,AS_OF)

def test_pair_does_not_reuse_single_scratch_input():
    p,b,e=inputs()
    changed,accepted=reviewed_impact_pool(p,['0','1'],e,AS_OF)
    assert accepted.empty
    assert changed.loc[changed.fanduel_id.eq('10'),'adjusted_fd_points'].iat[0]==30
    assert not changed.loc[changed.fanduel_id.isin(['0','1']),'eligible'].any()

def test_no_ambiguous_duplicate_inputs():
    p,b,e=inputs()
    with pytest.raises(ValueError,match='Ambiguous'):
        reviewed_impact_pool(p,['0'],pd.concat([e,e]),AS_OF)
