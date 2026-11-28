from datetime import date,timedelta
import pytest
from nba_short_window_distribution import compare,score

DAY=date(2026,11,1)
def fixture():
    rows=[]
    for i in range(8):
        for pid,team,shift in [('1','BOS',0),('2','NYK',2)]:
            rows.append(dict(game_date=(DAY+timedelta(days=i)).isoformat(),
                nba_id=pid,team=team,game='BOS@NYK',source='https://www.nba.com/game/test/box-score',
                minutes=5 if i==2 else 25,points=10+i+shift,reboundsTotal=4,assists=3,
                steals=1,blocks=0,turnovers=1))
    return rows

def test_identical_centers_and_earlier_date_only_training():
    rows=fixture()
    result=compare(rows,DAY+timedelta(days=8),minimum_rows=4,minimum_dates=2)
    assert len(result)==12
    first=[r for r in result if r['date']=='2026-11-07']
    assert len(first)==6
    assert all(r['earlier_rows']==4 and r['earlier_dates']==2 and r['short_prior'] for r in first)
    for pid in ('1','2'):
        group=[r for r in first if r['nba_id']==pid]
        assert len(group)==3
        assert all(r['mean_bias']==pytest.approx(group[0]['mean_bias']) for r in group)
    changed=[dict(r,points=100) if r['game_date']=='2026-11-07' else r for r in rows]
    new=[r for r in compare(changed,DAY+timedelta(days=8),4,2) if r['date']=='2026-11-07']
    for a,b in zip(first,new):
        assert a['width']==pytest.approx(b['width'])
        assert a['center']==b['center']
        assert a['actual']!=b['actual']

def test_invalid_windows_not_skipped_and_minimum_gate():
    rows=fixture()
    assert compare(rows,DAY+timedelta(days=8))==[]
    bad=[dict(r,assists=None) if r['nba_id']=='1' and r['game_date']=='2026-11-05' else r for r in rows]
    assert not any(r['nba_id']=='1' for r in compare(bad,DAY+timedelta(days=8),1,1))
    duplicate=rows+[dict(rows[4])]
    assert not any(r['nba_id']=='1' and r['date']=='2026-11-07'
                   for r in compare(duplicate,DAY+timedelta(days=8),1,1))

def test_proper_scores_for_point_mass():
    r=score([10,10,10],15)
    assert r['crps']==pytest.approx(5)
    assert r['coverage']==0
    assert r['upper_miss']==1
    assert r['interval_score']==50
