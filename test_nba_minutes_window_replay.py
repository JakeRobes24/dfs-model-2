from datetime import date,timedelta
import pytest
from nba_minutes_window_replay import compare_minutes_windows

DAY=date(2026,11,10)
def fixture():
    return [dict(game_date=(DAY+timedelta(days=i)).isoformat(),nba_id='1',
        player='Player A',team='BOS',game='BOS@NYK',
        source='https://www.nba.com/game/test/box-score',minutes=m,
        points=10,reboundsTotal=2,assists=1,steals=0,blocks=0,turnovers=1)
        for i,m in enumerate([4,20,24,28,18])]

def test_short_played_observation_is_retained_and_target_not_used():
    data=fixture()
    row,=compare_minutes_windows(data,DAY+timedelta(days=5))
    assert row['short_prior']
    assert row['mean4']==19
    assert row['median4']==22
    assert row['weighted4']==pytest.approx(22.8)
    data[-1]['minutes']=3
    changed,=compare_minutes_windows(data,DAY+timedelta(days=5))
    assert changed['mean4']==row['mean4']
    assert changed['rate']==row['rate']
    assert changed['actual_minutes']==3

def test_prior_absence_is_explicit_and_never_inferred_from_missing_log():
    data=fixture()
    data[-1]['game_date']=(DAY+timedelta(days=5)).isoformat()
    peer=dict(data[-2],game_date=(DAY+timedelta(days=4)).isoformat(),
        nba_id='2',player='Player B',teammates_absent=['playera'],teammates_played=['playerb'])
    row,=compare_minutes_windows(data+[peer],DAY+timedelta(days=6))
    assert row['explicit_prior_absence']
    row,=compare_minutes_windows(data+[dict(peer,teammates_absent=[])],DAY+timedelta(days=6))
    assert not row['explicit_prior_absence']

def test_incomplete_duplicate_and_stale_inputs_not_skipped():
    data=fixture()
    assert compare_minutes_windows(data+[dict(data[1])],DAY+timedelta(days=5))==[]
    assert compare_minutes_windows([dict(r,assists=None) if i==1 else r for i,r in enumerate(data)],
                                   DAY+timedelta(days=5))==[]
    data[-1]['game_date']=(DAY+timedelta(days=12)).isoformat()
    assert compare_minutes_windows(data,DAY+timedelta(days=13))==[]
