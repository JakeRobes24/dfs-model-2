from datetime import date,timedelta
import pytest
from nba_stock_replay import stock_replay

DAY=date(2026,11,1)
def records():
    rows=[]
    for i in range(5):
        for pid,team,stl in [('1','BOS',2),('2','NYK',0)]:
            rows.append(dict(game_date=(DAY+timedelta(days=i)).isoformat(),nba_id=pid,
                             team=team,game='BOS@NYK',source='https://www.nba.com/game/test/box-score',
                             minutes=25,points=10,reboundsTotal=5,assists=2,steals=stl,blocks=0,turnovers=1))
    return rows

def test_stocks_only_shrinkage_and_no_same_date_leakage():
    data=records()
    rows,_=stock_replay(data,DAY+timedelta(days=5))
    p=next(r for r in rows if r['nba_id']=='1')
    assert p['four_game_stock']==6
    assert p['pooled_100min_stock']==pytest.approx(4.5)
    assert p['pooled_100min_fd']==pytest.approx(p['four_game_fd']-1.5)
    for r in data[-2:]:
        r['steals']=10
        r['points']=30
    changed,_=stock_replay(data,DAY+timedelta(days=5))
    assert [r['pooled_100min_fd'] for r in changed]==[r['pooled_100min_fd'] for r in rows]

def test_short_or_duplicate_history_never_skipped():
    data=records()
    data[2]['minutes']=9
    rows,_=stock_replay(data,DAY+timedelta(days=5))
    assert [r['nba_id'] for r in rows]==['2']
    data=records()+[records()[0]]
    rows,_=stock_replay(data,DAY+timedelta(days=5))
    assert [r['nba_id'] for r in rows]==['2']

def test_cutoff_and_same_support():
    assert stock_replay(records(),DAY+timedelta(days=4))[0]==[]
    assert stock_replay(records(),DAY+timedelta(days=5),window=8)[0]==[]
