from datetime import date,timedelta
import pytest
from nba_component_pool_replay import component_pool_replay,CHANNELS

DAY=date(2026,11,1)

def fixture():
    rows=[]
    for i in range(5):
        for pid,team,pts,reb,ast,stl in [('1','BOS',20,8,6,2),('2','NYK',10,2,0,0)]:
            rows.append(dict(game_date=(DAY+timedelta(days=i)).isoformat(),nba_id=pid,
                             team=team,game='BOS@NYK',source='https://www.nba.com/game/test/box-score',
                             minutes=25,points=pts,reboundsTotal=reb,assists=ast,steals=stl,blocks=0,
                             turnovers=2,fieldGoalsAttempted=10,freeThrowsAttempted=0))
    return rows

def test_component_pool_holds_minutes_and_other_components_fixed():
    data=fixture()
    rows,_=component_pool_replay(data,DAY+timedelta(days=5))
    a=next(r for r in rows if r['nba_id']=='1')
    assert a['minutes']==25
    assert a['base_fd']==pytest.approx(42.6)
    assert a['pool_stocks']==pytest.approx(4.5)
    assert a['pool_reb']==pytest.approx(7.8)
    assert a['pool_ast']==pytest.approx(6.75)
    assert a['pool_net']==pytest.approx((72+40*13/12)/(48+40)*12)
    for k in CHANNELS:
        assert a[f'only_{k}_fd']==pytest.approx(a['base_fd']-a[f'base_{k}']+a[f'pool_{k}'])
    assert a['all_pool_fd']==pytest.approx(sum(a[f'pool_{k}'] for k in CHANNELS))

def test_target_day_never_enters_any_forecast():
    data=fixture()
    rows,_=component_pool_replay(data,DAY+timedelta(days=5))
    for r in data[-2:]:
        r.update(points=99,reboundsTotal=30,assists=15,steals=10)
    new,_=component_pool_replay(data,DAY+timedelta(days=5))
    for a,b in zip(rows,new):
        assert a['all_pool_fd']==b['all_pool_fd']
        assert a['actual_fd']!=b['actual_fd']

def test_missing_and_duplicate_history_not_skipped():
    data=fixture()
    data[2]['assists']=None
    rows,_=component_pool_replay(data,DAY+timedelta(days=5))
    assert [r['nba_id'] for r in rows]==['2']
    data=fixture()
    data.append(dict(data[0]))
    rows,_=component_pool_replay(data,DAY+timedelta(days=5))
    assert [r['nba_id'] for r in rows]==['2']
    assert component_pool_replay(fixture(),DAY+timedelta(days=4))[0]==[]
