from datetime import date,timedelta
import pytest
from nba_preview_triage import review_preview

def fixture():
    day=date(2026,11,25)
    p=dict(slate_date='2026-11-27',observed_at='2026-11-26T12:00:00Z',
        forecasts={'NBA House':[dict(player='Alpha Player',team='BOS',game='BOS@NYK',minutes=30)],
        'PropSims':[dict(player='Alpha Player',team='BOS',game='BOS@NYK',minutes=36,fd_points=40)]})
    h=[dict(player='Alpha Player',nba_id='101',team='BOS',game='BOS@NYK',
        game_date=(day-timedelta(days=7-i)).isoformat(),source='https://www.nba.com/game/x/box-score',
        minutes=28,started=True,points=15,reboundsTotal=5,assists=4,steals=1,blocks=0,
        turnovers=2,fieldGoalsAttempted=10,freeThrowsAttempted=4) for i in range(8)]
    return p,h

def test_exact_history_and_disagreements():
    p,h=fixture()
    r=review_preview(p,h)[0]
    assert r['history_games']==8 and r['last8_minutes']==28 and r['last_role']=='starter'
    assert r['last8_fppm']==pytest.approx(28/28)
    assert r['provider_gap']==6 and r['propsims_vs_history']==8
    assert len(r['review_reasons'])==2
    assert 'unknown' in r['official_status']

def test_future_and_conflicting_identity_rejected():
    p,h=fixture()
    assert review_preview(p,h+[dict(h[-1],game_date='2026-11-27',minutes=50)])[0]['last8_minutes']==28
    assert review_preview(p,h+[dict(h[-1],nba_id='999')])[0]['history_games']==0
    h[-1]['team']='NYK'
    assert review_preview(p,h)[0]['history_games']==0

def test_duplicate_or_incomplete_window_not_skipped():
    p,h=fixture()
    assert review_preview(p,h+[dict(h[-1])])[0]['last8_minutes'] is None
    h[-1]['assists']=None
    assert review_preview(p,h)[0]['last8_fppm'] is None

def test_report_timestamp_and_exact_match():
    p,h=fixture()
    r=dict(player='Alpha Player',team='BOS',game='BOS@NYK',official=True,status='out',observed_at='2026-11-26T11:00:00Z')
    assert review_preview(p,h,[r])[0]['official_status']=='out'
    r['observed_at']='2026-11-26T13:00:00Z'
    assert 'unknown' in review_preview(p,h,[r])[0]['official_status']
