from datetime import date,timedelta
import pytest
from nba_component_history import compare_component_history,POLICIES

def sample():
    rows=[]
    for i in range(6):
        rows.append(dict(nba_id='101',team='BOS',game='BOS@NYK',
            source='https://www.nba.com/game/bos-vs-nyk/box-score',
            game_date=(date(2026,11,10)+timedelta(days=i)).isoformat(),
            started=i>=2,minutes=30+i,points=15+i,reboundsTotal=5,assists=4,
            steals=1,blocks=0,turnovers=2,fieldGoalsAttempted=12+i,freeThrowsAttempted=4))
    return rows

def run(rows):
    return compare_component_history(rows,cutoff_day='2026-11-26')

def test_same_sample_all_policies_and_component_identity():
    rows=sample()
    report=run(rows)
    assert len(report['rows'])==2*len(POLICIES)
    assert all(r['player_games']==2 for r in report['summary'])
    first=next(r for r in report['rows'] if r['policy']=='four_game_mean')
    points=lambda r:r['points']+1.2*r['reboundsTotal']+1.5*r['assists']+3*r['steals']+3*r['blocks']-r['turnovers']
    assert first['predicted_fd']==pytest.approx(sum(points(r) for r in rows[:4])/4)
    assert first['actual_fd']==pytest.approx(points(rows[4]))
    assert all(max(r['training_dates'])<r['date'] for r in report['rows'])
    assert not report['certified']

def test_heldout_target_stats_and_role_cannot_change_own_forecast():
    rows=sample()
    a=run(rows)
    rows[-1]['points']=100
    rows[-1]['started']=False
    b=run(rows)
    assert [r['predicted_fd'] for r in a['rows']]==[r['predicted_fd'] for r in b['rows']]
    assert a['summary']!=b['summary']

def test_incomplete_intermediate_game_blocks_window_instead_of_skipping():
    rows=sample()
    rows[2].pop('assists')
    r=run(rows)
    assert not r['rows']
    assert r['rejected']['incomplete_or_short_window']==2

def test_duplicate_date_and_future_excluded():
    rows=sample()
    assert not run(rows+[dict(rows[2])])['rows']
    a=run(rows)
    b=run(rows+[dict(rows[-1],game_date='2026-11-26')])
    assert a['rows']==b['rows']

def test_no_team_or_identity_transfer():
    rows=sample()
    rows[-1]['team']='NYK'
    rows[-2]['nba_id']='202'
    assert not run(rows)['rows']

def test_unknown_role_falls_back_to_equal():
    rows=sample()
    for r in rows:r['started']=None
    out=run(rows)['rows']
    for d in {r['date'] for r in out}:
        a={r['policy']:r['predicted_fd'] for r in out if r['date']==d}
        assert a['persistent_role_prior']==pytest.approx(a['four_game_mean'])
