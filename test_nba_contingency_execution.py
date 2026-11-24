"""Exact-entry, current-status and lock checks for prepared alternatives."""
import pandas as pd
import pytest
from model import SLOTS
from nba_contingency_execution import plan_contingency_entry
AS_OF='2026-11-23T23:00:00Z'
def fixture():
    ids=[str(i) for i in range(11)]
    p=pd.DataFrame(dict(fanduel_id=ids,fanduel_name=['Player '+i for i in ids],
        team='CHA',salary=6000,eligible=True,adjusted_fd_points=[30.]*9+[40.,25.],
        roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL'))
    b=pd.DataFrame({'slot':SLOTS,'fanduel_id':ids[:9]})
    t=b.copy();t.loc[0,'fanduel_id']='9';t['lineup']=1
    a=pd.DataFrame([dict(fanduel_id='0',official=True,status='out',source='NBA',
        observed_at='2026-11-23T22:55:00Z',review='Reviewed')])
    return p,b,t,a

def test_preview_is_hypothetical_and_reuses_current_scores():
    p,b,t,a=fixture()
    report=plan_contingency_entry(p,b,t,['0'])
    assert report['status']=='hypothetical_preview'
    option=report['options'][0]
    assert option['steps'][0]['out_id']=='0' and option['steps'][0]['in_id']=='9'
    assert option['current_fd_points']==280
    assert option['salary']==54000 and p.eligible.all()

def test_activation_requires_current_official_status_and_verified_locks():
    p,b,t,a=fixture()
    with pytest.raises(ValueError,match='verified locks'):
        plan_contingency_entry(p,b,t,['0'],preview=False,audit=a,as_of=AS_OF)
    report=plan_contingency_entry(p,b,t,['0'],preview=False,audit=a,as_of=AS_OF,schedule_verified=True)
    assert report['status']=='validated_at_snapshot'

@pytest.mark.parametrize('change',[{'official':False},{'review':'Stale'},
    {'observed_at':'2026-11-23T23:10:00Z'},{'observed_at':'2026-11-23T12:00:00Z'},
    {'status':'available'}])
def test_stale_future_unofficial_or_available_rejected(change):
    p,b,t,a=fixture()
    with pytest.raises(ValueError,match='not confirmed'):
        plan_contingency_entry(p,b,t,['0'],preview=False,schedule_verified=True,as_of=AS_OF,audit=a.assign(**change))

def test_same_timestamp_conflict_rejected():
    p,b,t,a=fixture()
    with pytest.raises(ValueError,match='not confirmed'):
        plan_contingency_entry(p,b,t,['0'],preview=False,schedule_verified=True,as_of=AS_OF,
                               audit=pd.concat([a,a.assign(status='available')]))

def test_locked_scratch_is_immutable():
    p,b,t,a=fixture()
    assert plan_contingency_entry(p,b,t,['0'],closed_players=['0'])['status']=='blocked_locked_scratch'

def test_newly_closed_replacement_blocked():
    p,b,t,a=fixture()
    assert not plan_contingency_entry(p,b,t,['0'],closed_players=['9'])['options']

def test_retained_ineligible_open_player_blocks():
    p,b,t,a=fixture()
    p.loc[p.fanduel_id.eq('1'),'eligible']=False
    assert not plan_contingency_entry(p,b,t,['0'])['options']

def test_wrong_player_or_invalid_slot_rejected():
    p,b,t,a=fixture()
    t.loc[0,'fanduel_id']='unknown'
    assert not plan_contingency_entry(p,b,t,['0'])['options']
    t.loc[0,'fanduel_id']='9'
    p.loc[p.fanduel_id.eq('9'),'roster_eligibility']='SG'
    assert not plan_contingency_entry(p,b,t,['0'])['options']
