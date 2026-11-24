"""Controlled fixtures for bounded injury contingencies."""
import pandas as pd
import pytest
import nba_injury_contingency as c
from model import SLOTS

def fixture():
    rows=[]
    for i in range(12):
        rows.append(dict(fanduel_id=str(i),fanduel_name='Player '+str(i),salary=6000,
            roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL',eligible=True,
            confidence='high',adjusted_fd_points=40.-i,adjusted_minutes=30.,
            minutes_method='fixture',injury_flag='Q' if i in (0,1) else '',
            prelock_status='available' if i==1 else ''))
    pool=pd.DataFrame(rows)
    base=pd.DataFrame({'lineup':1,'slot':SLOTS,'fanduel_id':[str(i) for i in range(9)]})
    return pool,base

def test_real_solver_contingency():
    p,b=fixture()
    report=c.prepare_contingencies(p,b,time_budget_seconds=10)
    assert report['uncertain_selected_players']==1
    assert report['completed_scenarios']==1
    scenario=report['scenarios'][0]
    assert scenario['out_id']=='0' and scenario['status']=='complete'
    candidate=scenario['candidates']
    assert len(candidate)==9 and candidate.fanduel_id.nunique()==9
    assert '0' not in candidate.fanduel_id.tolist()
    assert candidate.salary.sum()<=60000
    assert p.eligible.all()
    pd.testing.assert_frame_equal(report['baseline'],b)

def test_budget_and_limit_are_visible(monkeypatch):
    p,b=fixture()
    p.loc[p.fanduel_id.eq('1'),'prelock_status']='questionable'
    times=iter([0.,2.,2.])
    monkeypatch.setattr(c,'monotonic',lambda:next(times))
    report=c.prepare_contingencies(p,b,time_budget_seconds=1)
    assert report['completed_scenarios']==0
    assert len(report['scenarios'])==2
    assert all(r['status']=='not_run_budget_or_limit' for r in report['scenarios'])

def test_invalid_baseline_rejected():
    p,b=fixture()
    b.loc[8,'fanduel_id']='0'
    with pytest.raises(ValueError,match='Invalid baseline'):
        c.prepare_contingencies(p,b)

def test_partial_does_not_replace_baseline(monkeypatch):
    p,b=fixture()
    monkeypatch.setattr(c,'optimize',lambda *a,**kw:pd.DataFrame())
    report=c.prepare_contingencies(p,b)
    assert report['scenarios'][0]['status']=='partial_or_infeasible'
    pd.testing.assert_frame_equal(report['baseline'],b)
