from datetime import date,timedelta
import json
import pandas as pd
import pytest
from nba_window_shadow import attach_window_inputs,freeze_history_windows,compare_frozen_history_windows,POLICIES
from slate_replay_capture import capture_pool,build_replay_rows

DAY=date(2026,11,27)
CAP='2026-11-27T20:00:00Z'
TIP='2026-11-28T00:00:00Z'
def pool():
    return pd.DataFrame([dict(fanduel_id='137200-1',fanduel_name='Player A',team='BOS',game='BOS@NYK',
        eligible=True,injury_flag='',prelock_status='',prelock_starter='starter',
        projected_minutes=30,projected_fd_points=30,adjusted_minutes=30,adjusted_fd_points=30)])
def logs():
    return [dict(nba_id='101',player='Player A',team='BOS',game='BOS@NYK',
        source='https://www.nba.com/game/bos-vs-nyk/box-score',
        game_date=DAY-timedelta(days=8-i),minutes=32,points=24 if i<4 else 16,
        reboundsTotal=5,assists=4,steals=1,blocks=0,turnovers=2,
        fieldGoalsAttempted=15,freeThrowsAttempted=4) for i in range(8)]
def saved(p=None,history=None):
    f=attach_window_inputs(pool() if p is None else p,logs() if history is None else history,DAY)
    schedule=[dict(awayTeam={'teamTricode':'BOS'},homeTeam={'teamTricode':'NYK'},gameTimeUtc=TIP)]
    return capture_pool(f,pd.DataFrame(),schedule,DAY,CAP,('a'*64,'b'*64))
def replay(f):
    results=pd.DataFrame([dict(fanduel_id='137200-1',outcome='Played',nba_actual_minutes=32,
                              nba_fd_points=33,nba_source='NBA box',recorded_fd_points=33)])
    return build_replay_rows(f,results,DAY)

def test_four_and_eight_rate_challengers_same_sample_and_score_unchanged():
    f=saved()
    pd.testing.assert_frame_equal(f[pool().columns],pool())
    assert f.shadow_hw_rate4.iloc[0]==pytest.approx(.8*30+.2*30*29/32)
    assert f.shadow_hw_rate8.iloc[0]==pytest.approx(.8*30+.2*30*33/32)
    assert f.shadow_hw_minutes8.iloc[0]==pytest.approx(30.4)
    assert compare_frozen_history_windows(replay(f))['Paired players'].tolist()==[1]*4

def test_missing_incomplete_duplicate_and_mixed_identity_rejected():
    for history in [logs()[:-1], logs()+[dict(logs()[0])],
                    [dict(r,nba_id='202') if i==0 else r for i,r in enumerate(logs())],
                    [dict(r,assists=None) if i==0 else r for i,r in enumerate(logs())]]:
        f=saved(history=history)
        assert f[list(POLICIES.values())].isna().all().all()

def test_same_day_outcomes_cannot_enter_history():
    f=saved(history=logs()+[dict(logs()[0],game_date=DAY,points=100)])
    pd.testing.assert_frame_equal(f,saved())

def test_frozen_tamper_and_timestamp_fail_closed():
    r=replay(saved())
    assert compare_frozen_history_windows(r.assign(shadow_hw_rate4=99))['Paired players'].tolist()==[0]*4
    assert compare_frozen_history_windows(r.assign(shadow_hw_captured_at='2026-11-27T20:01:00Z'))['Paired players'].tolist()==[0]*4

def test_uncertain_status_and_post_tip_hold():
    f=saved(p=pool().assign(injury_flag='Q'))
    assert f[list(POLICIES.values())].isna().all().all()
    f=saved().assign(replay_before_full_slate_tip=False)
    assert compare_frozen_history_windows(f)['Paired players'].tolist()==[0]*4

def test_multislate_prospective_roundtrip():
    from nba_shadow_multislate import compare_across_slates
    r=replay(saved())
    _,summary=compare_across_slates(r)
    rows=summary.loc[summary.Policy.isin(POLICIES)]
    assert len(rows)==4 and rows['Paired players'].eq(1).all()
    assert rows.Period.eq('Prospective').all()
    assert rows['Review status'].eq('Insufficient prospective evidence').all()


def test_candidate_window_sensitivity_keeps_unsupported_players_at_reviewed_scores():
    from nba_window_shadow import candidate_window_sensitivity
    from model import SLOTS
    base=pool()
    rows=[dict(base.iloc[0],fanduel_id=f'137200-{i}',fanduel_name=f'Player {i}',
               team=['BOS','NYK','ORL'][i%3],salary=6000,
               roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL')
          for i in range(1,11)]
    rows[0].update(fanduel_name='Player A',team='BOS')
    frame=attach_window_inputs(pd.DataFrame(rows),logs(),DAY)
    candidates=pd.DataFrame([dict(lineup=j,slot=slot,fanduel_id=pid)
         for j,ids in [(1,list(frame.fanduel_id.iloc[:9])),(2,list(frame.fanduel_id.iloc[1:]))]
         for slot,pid in zip(SLOTS,ids)])
    original=frame.copy(deep=True)
    result=candidate_window_sensitivity(frame,candidates,DAY).set_index('Lineup')
    assert result['Reviewed FD'].tolist()==[270,270]
    assert result['Supported players'].tolist()==[1,0]
    assert result['Unchanged fallback players'].tolist()==[8,9]
    for name in POLICIES:
        assert result.loc[2,name+' delta']==0
    assert result.loc[1,'8-game historical minutes and rate (20%) FD']==pytest.approx(240+30.4*(.8+.2*33/32))
    pd.testing.assert_frame_equal(frame,original)
    with pytest.raises(ValueError,match='no longer eligible'):
        candidate_window_sensitivity(frame.assign(eligible=~frame.fanduel_id.eq('137200-1')),candidates,DAY)


def test_workload_cohort_support_separate_from_verified_outcomes():
    first=saved()
    second=saved(p=pool().assign(fanduel_id='137200-2',fanduel_name='Player B',
                                 adjusted_minutes=15,adjusted_fd_points=15),
                 history=[dict(r,player='Player B',nba_id='102') for r in logs()])
    third=saved(p=pool().assign(fanduel_id='137200-3',fanduel_name='Player C',
                                adjusted_minutes=25,adjusted_fd_points=25),history=[])
    r=replay(pd.concat([first,second,third],ignore_index=True))
    report=compare_frozen_history_windows(r,by_projected_minutes=True)
    counts=report.groupby('Cohort').first()
    assert counts.loc['10 to <20','Eligible pre-tip players']==1
    assert counts.loc['10 to <20','Frozen supported players']==1
    assert counts.loc['10 to <20','Paired players']==0
    assert pd.isna(counts.loc['10 to <20','Shadow MAE'])
    assert counts.loc['20 to <30','Eligible pre-tip players']==1
    assert counts.loc['20 to <30','Frozen supported players']==0
    assert counts.loc['30 to 48','Paired players']==1
    total=compare_frozen_history_windows(r)
    assert total['Frozen supported players'].tolist()==[2]*4
    assert total['Paired players'].tolist()==[1]*4
    # Check the entire receipt before partitioning; each subgroup alone
    # would otherwise accept its own unrelated input fingerprint.
    r.loc[r.fanduel_id.eq('137200-2'),'replay_daily_sha256']='c'*64
    bad=compare_frozen_history_windows(r,by_projected_minutes=True)
    assert bad['Paired players'].eq(0).all()
    assert 'Eligible pre-tip players' not in bad


def test_history_window_missing_or_malformed_input_fingerprints_fail_closed():
    r=replay(saved())
    for bad in (r.drop(columns='replay_daily_sha256'),
                r.assign(replay_contest_sha256='bad')):
        assert compare_frozen_history_windows(bad)['Paired players'].tolist()==[0]*4
    f=saved().drop(columns='replay_daily_sha256')
    clean=f.drop(columns=['shadow_hw_version','shadow_hw_captured_at',*POLICIES.values()])
    assert not set(POLICIES.values()) & set(freeze_history_windows(clean))
