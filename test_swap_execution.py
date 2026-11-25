"""Tests for slot reassignment and executable swaps; synthetic regression inputs."""
import pytest
from swap_execution import plan_edits, assign_for_execution, SLOTS

def fixture():
    before = tuple(str(i) for i in range(9))
    players = {p: dict(salary=6500, slots={s}, name=p, team=['CHA','BOS','CHA','BOS','NYK','NYK','CHA','BOS','NYK'][int(p)])
               for p,s in zip(before,SLOTS)}
    players['3']['slots'].update({'C','UTIL'})
    players['4']['slots'].update({'PF','UTIL'})
    players['7']['slots'].update({'PF','UTIL'})
    players['8']['slots'].update({'SG','UTIL'})
    players['1']['salary']=7500
    players['8']['salary']=6000
    players['0']['salary']=7500
    players['cheap']=dict(salary=6200,slots={'F/C'},name='Cheap',team='CHA')
    players['quickley']=dict(salary=6300,slots={'PG','UTIL'},name='Quickley',team='TOR')
    players['new']=dict(salary=6500,slots={'PF','C'},name='New',team='CHA')
    return before, players

def test_savings_before_utility_move():
    b,p=fixture()
    a=list(b);a[6]='cheap';a[8]='quickley';a[1]='8'
    r=plan_edits(b,a,p)
    assert [s['slot'] for s in r['steps']]==['F/C','UTIL 2','SG']
    assert all(s['salary_after']<=60000 for s in r['steps'])

def test_reassignment_avoids_unnecessary_move():
    b,p=fixture()
    a=list(b);a[3]='4';a[4]='new'
    roster, r=assign_for_execution(b,a,p)
    assert set(roster)==set(a)
    assert len(r['steps'])==1
    assert roster[4]=='4'

def test_locked_move_rejected():
    b,p=fixture();a=list(b);a[8]='quickley';a[1]='8'
    with pytest.raises(ValueError,match='Started'):
        plan_edits(b,a,p,{'8'})

def test_cycle_does_not_become_actionable():
    b,p=fixture();a=list(b);a[7],a[8]=a[8],a[7]
    assert plan_edits(b,a,p)['mode']=='multi_slot_unverified'
    roster,r=assign_for_execution(b,a,p)
    assert roster==b and r['mode']=='no_change'

def test_wrong_slot_rejected():
    b,p=fixture();a=list(b);a[1]='quickley'
    with pytest.raises(ValueError,match='slot'):
        plan_edits(b,a,p)

def test_two_util_unique():
    b,p=fixture();a=list(b);a[8]=a[7]
    with pytest.raises(ValueError,match='unique'):
        plan_edits(b,a,p)
