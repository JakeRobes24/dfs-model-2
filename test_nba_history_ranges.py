from datetime import date,timedelta
import pytest
from nba_history_ranges import compare_history_ranges,historical_forecasts,_interval_score,POLICIES

def fixture():
    rows=[]
    for i in range(16):
        for p in range(25):
            rows.append(dict(nba_id=str(p+1),team='BOS',game='BOS@NYK',
                source='https://www.nba.com/game/bos-vs-nyk/box-score',
                game_date=(date(2026,11,1)+timedelta(days=i)).isoformat(),
                minutes=22+(p+i)%12,points=12+(p+2*i)%15,reboundsTotal=5,
                assists=4,steals=1,blocks=0,turnovers=2,
                fieldGoalsAttempted=12+(p+i)%8,freeThrowsAttempted=4))
    return rows
def run(r):
    return compare_history_ranges(r,cutoff_day='2026-11-26',draws=200)

def test_matched_policies_and_chronology():
    r=run(fixture())
    assert r['forecast_rows']==200
    assert len(r['warmup_dates'])==5
    assert {s['player_games'] for s in r['summary']}=={75}
    assert {s['policy'] for s in r['summary']}==set(POLICIES)
    assert all(x['training_latest']<x['date'] and x['p10']<=x['p50']<=x['p90'] for x in r['rows'])
    assert not r['certified']

def test_target_outcome_not_used_for_own_range():
    f=fixture()
    a=run(f)
    f[-1]['points']=100
    b=run(f)
    keys=('date','nba_id','policy','p10','p50','p90')
    assert [[r[k] for k in keys] for r in a['rows']]==[[r[k] for k in keys] for r in b['rows']]
    assert a['summary']!=b['summary']

def test_repeatability():
    f=fixture()
    assert run(f)==run(f)

def test_missing_history_or_duplicate_not_silently_skipped():
    f=fixture()
    f[0].pop('assists')
    rows=historical_forecasts(f,cutoff_day='2026-11-26')
    assert not any(r['nba_id']=='1' and r['date']=='2026-11-09' for r in rows)
    f=fixture()
    rows=historical_forecasts(f+[dict(f[0])],cutoff_day='2026-11-26')
    assert not any(r['nba_id']=='1' and r['date']=='2026-11-09' for r in rows)

def test_warmup_and_interval_score():
    assert not run(fixture()[:12*25])['summary']
    assert _interval_score(5,0,10)==10
    assert _interval_score(12,0,10)==30
    assert _interval_score(-2,0,10)==30

def test_invalid_draws():
    with pytest.raises(ValueError):compare_history_ranges([],cutoff_day='2026-11-26',draws=0)
