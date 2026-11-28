from datetime import date,timedelta
import pytest
from nba_absence_history import compare_absence_persistence,POLICIES

def fixture():
    rows=[]
    for i in range(9):
        d=(date(2026,11,1)+timedelta(days=i)).isoformat()
        absent=i>=4
        r=dict(nba_id='101',player='Player A',team='BOS',game='BOS@NYK',
            source='https://www.nba.com/game/bos-vs-nyk/box-score',game_date=d,
            started=True,minutes=30,points=30 if absent else 15,
            reboundsTotal=5,assists=4,steals=1,blocks=0,turnovers=2,
            fieldGoalsAttempted=20 if absent else 10,freeThrowsAttempted=4,
            teammates_played=('playerb',) if not absent else (),
            teammates_absent=('playerb',) if absent else ())
        rows.append(r)
        if not absent:
            rows.append(dict(r,nba_id='202',player='Player B',teammates_played=('playera',),
                             teammates_absent=()))
    return rows

def run(rows):
    return compare_absence_persistence(rows,cutoff_day='2026-11-26')

def test_absence_same_rows_and_target_state_never_filters():
    f=fixture()
    a=run(f)
    assert len(a['rows'])==len(POLICIES)
    assert a['observed_target_teammate_states']=={'absent':1}
    target=f[-1]
    target['teammates_absent']=()
    target['teammates_played']=('playerb',)
    target['started']=False
    target['points']=0
    b=run(f)
    assert b['observed_target_teammate_states']=={'played':1}
    assert [r['prediction'] for r in a['rows']]==[r['prediction'] for r in b['rows']]
    assert all(max(r['training_dates'])<r['date'] for r in a['rows'])

def test_shrink_and_no_double_counting():
    r={r['policy']:r for r in run(fixture())['rows']}
    assert r['absence_both']['prediction']>r['same_role_mean']['prediction']
    assert r['absence_both']['prediction']<r['four_game_mean']['prediction']
    assert r['absence_minutes_only']['prediction']==pytest.approx(r['same_role_mean']['prediction'])

def test_unknown_or_conflicting_prior_participation_rejected():
    f=fixture()
    f[-2]['teammates_played']=('playerb',)
    assert not run(f)['rows']
    f=fixture()
    for r in f:
        if r['nba_id']=='101' and r['teammates_played']:
            r['teammates_played']=()
    assert not run(f)['rows']

def test_ambiguous_teammate_identity_rejected():
    f=fixture()
    f[1]['nba_id']='303'
    assert not run(f)['rows']

def test_future_identity_does_not_change_earlier_predictions():
    f=fixture()
    a=run(f)['rows']
    future=dict(f[1],nba_id='303',game_date='2026-11-10')
    assert run(f+[future])['rows']==a

def test_role_mismatch_blocks_support():
    f=fixture()
    for r in f:
        if r['nba_id']=='101' and r['teammates_played']:
            r['started']=False
    assert not run(f)['rows']
