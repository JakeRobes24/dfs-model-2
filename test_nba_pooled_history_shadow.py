from datetime import date,timedelta
import json
import pandas as pd
import pytest

from nba_pooled_history_shadow import (attach_pooled_history,pooled_prediction,
    compare_frozen_pooled_history,FROZEN_FIELDS,PRIOR,POLICIES)
from slate_replay_capture import capture_pool,build_replay_rows

DAY=date(2026,11,28)
NOW='2026-11-28T20:00:00Z'
TIP='2026-11-28T23:00:00Z'


def fixture():
    p=pd.DataFrame([dict(fanduel_id='137300-1',fanduel_name='Player A',team='BOS',game='BOS@NYK',
        eligible=True,injury_flag='',prelock_status='',prelock_starter='starter',
        projected_minutes=25,projected_fd_points=32,adjusted_minutes=30,adjusted_fd_points=38)])
    logs=[dict(nba_id='101',player='Player A',team='BOS',game='BOS@NYK',
        source='https://www.nba.com/game/bos-vs-nyk/box-score',
        game_date=DAY-timedelta(days=4-i),minutes=25,points=20,reboundsTotal=8,assists=6,
        steals=2,blocks=1,turnovers=2,fieldGoalsAttempted=10,freeThrowsAttempted=0) for i in range(4)]
    schedule=[dict(awayTeam={'teamTricode':'BOS'},homeTeam={'teamTricode':'NYK'},gameTimeUtc=TIP)]
    return p,logs,schedule


def test_fixed_prior_preserves_personal_rebounding_and_reviewed_minutes():
    p,logs,_=fixture()
    frame=attach_pooled_history(p,logs,DAY)
    a,b,raw=pooled_prediction(next(frame.itertuples()),DAY)
    parts=json.loads(raw)
    assert a==pytest.approx(30/25*(18+9.6+9+9))
    assert parts['pooled']['reb']==parts['personal']['reb']
    assert parts['pooled']['stocks']==pytest.approx(30*(36+100*PRIOR['stocks']/PRIOR['minutes'])/200)
    assert parts['pooled']['net']==pytest.approx(30/25*12*(72+40*PRIOR['net']/PRIOR['opp'])/88)
    assert b==pytest.approx(sum(parts['pooled'].values()))
    assert p.adjusted_fd_points.iloc[0]==38


def test_exact_pregame_capture_and_replay():
    p,logs,schedule=fixture()
    frame=attach_pooled_history(p,logs,DAY)
    cap=capture_pool(frame,pd.DataFrame(),schedule,DAY,NOW,('a'*64,'b'*64))
    assert set(FROZEN_FIELDS)<=set(cap)
    assert cap.pooled_hw_pooled_fd.notna().all()
    pd.testing.assert_frame_equal(cap[p.columns],p)
    results=pd.DataFrame([dict(fanduel_id='137300-1',outcome='Played',nba_actual_minutes=30,
        nba_fd_points=40,nba_source='NBA box',recorded_fd_points=None)])
    replay=build_replay_rows(cap,results,DAY)
    report=compare_frozen_pooled_history(replay)
    assert report['Paired players'].tolist()==[1,1]
    assert report['Reviewed MAE'].tolist()==[2,2]
    for bad in (replay.assign(pooled_hw_pooled_fd=99),
                replay.assign(pooled_hw_components_json='{}'),
                replay.assign(pooled_hw_captured_at='2026-11-28T20:01:00Z'),
                replay.assign(injury_flag='Q'),
                replay.assign(replay_contest_sha256='invalid')):
        assert compare_frozen_pooled_history(bad)['Paired players'].tolist()==[0,0]
    assert compare_frozen_pooled_history(replay.drop(columns='pooled_hw_pooled_fd'))['Paired players'].tolist()==[0,0]
    late=capture_pool(frame,pd.DataFrame(),schedule,DAY,TIP,('a'*64,'b'*64))
    assert 'pooled_hw_pooled_fd' not in late


def test_incomplete_recent_window_and_identity_are_not_imputed():
    p,logs,_=fixture()
    for history in (logs[:-1],logs+[dict(logs[0])],
                    [dict(r,assists=None) if i==0 else r for i,r in enumerate(logs)],
                    [dict(r,nba_id='999') if i==0 else r for i,r in enumerate(logs)]):
        frame=attach_pooled_history(p,history,DAY)
        assert pooled_prediction(next(frame.itertuples()),DAY) is None
    same_day=logs+[dict(logs[0],game_date=DAY,points=100)]
    pd.testing.assert_frame_equal(attach_pooled_history(p,logs,DAY),attach_pooled_history(p,same_day,DAY))
