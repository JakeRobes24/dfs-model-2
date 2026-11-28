import json
import pandas as pd
import pytest
from nba_consensus_history import forecast_consensus_history, compare_consensus_history, POLICIES
from nba_source_accuracy import MINUTE_SOURCES

CAP='2026-11-27T20:00:00Z'
TIP='2026-11-28T00:00:00Z'
STAMP='2026-11-27T19:00:00Z'
def fixture():
    sources=list(MINUTE_SOURCES.items())[:2]
    notes=[dict(source=s,independent_group=f,observed_at=STAMP,official=False,minutes=m)
           for (s,f),m in zip(sources,[28,32])]
    return pd.DataFrame([dict(fanduel_id='137200-1',team='BOS',game='BOS@NYK',eligible=True,
        adjusted_minutes=24,adjusted_fd_points=24,daily_minutes=22,daily_points=22,
        replay_captured_at_utc=CAP,replay_cutoff_utc=TIP,replay_timing='before_scheduled_tip',
        replay_before_full_slate_tip=True,projection_sources_json='[]',replay_evidence_json=json.dumps(notes),
        prelock_starter='starter',prelock_status='',injury_flag='',shadow_rate_sources='official prior games',
        shadow_recent_fppm=1.5,shadow_recent_games=4,shadow_recent_minutes=120,
        shadow_role_fppm=1.25,shadow_role_games=3,shadow_role_minutes=80,
        actual_points=36,actual_minutes=30,verified_outcome='played',nba_source='official')])

def test_factorial_prediction_and_identical_sample():
    f=fixture()
    out=forecast_consensus_history(f).iloc[0]
    assert out.consensus_minutes==30
    assert out.history_rate_weight==.25
    assert out.history_rate==pytest.approx(1.0625)
    assert out.consensus_minutes_fd==30
    assert out.historical_rate_fd==25.5
    assert out.consensus_history_fd==31.875
    report=compare_consensus_history(f)
    assert report['Paired players'].tolist()==[1,1,1]
    assert report['Shadow MAE'].tolist()==pytest.approx([6,10.5,4.125])

def test_forecast_does_not_read_outcomes():
    f=fixture()
    expected=forecast_consensus_history(f)
    f=f.drop(columns=['actual_points','actual_minutes','verified_outcome','nba_source'])
    pd.testing.assert_frame_equal(expected,forecast_consensus_history(f))

def test_post_news_stale_source_blocked_across_team():
    f=fixture()
    sibling=f.iloc[0].to_dict()
    sibling['fanduel_id']='137200-2'
    sibling['replay_evidence_json']=json.dumps([dict(official=True,status='out',observed_at='2026-11-27T19:30:00Z')])
    assert forecast_consensus_history(pd.concat([f,pd.DataFrame([sibling])],ignore_index=True)).empty

def test_same_family_duplicates_do_not_create_consensus():
    f=fixture()
    notes=json.loads(f.loc[0,'replay_evidence_json'])
    f.loc[0,'replay_evidence_json']=json.dumps([notes[0],notes[0]])
    assert forecast_consensus_history(f).empty

def test_conflicting_families_and_large_spread_held():
    f=fixture()
    notes=json.loads(f.loc[0,'replay_evidence_json'])
    notes.append(dict(notes[0],minutes=27))
    f.loc[0,'replay_evidence_json']=json.dumps(notes)
    assert forecast_consensus_history(f).empty
    f=fixture()
    notes=json.loads(f.loc[0,'replay_evidence_json'])
    notes[0]['minutes']=18
    f.loc[0,'replay_evidence_json']=json.dumps(notes)
    assert forecast_consensus_history(f).empty

def test_uncertain_role_or_missing_history_not_filled():
    f=fixture()
    f.loc[0,'injury_flag']='Q'
    assert forecast_consensus_history(f).empty
    f=fixture()
    f.loc[0,'shadow_rate_sources']=''
    assert forecast_consensus_history(f).empty

def test_post_tip_and_duplicate_contest_rows_fail_closed():
    f=fixture()
    f.loc[0,'replay_cutoff_utc']=CAP
    with pytest.raises(ValueError):forecast_consensus_history(f)
    f=fixture()
    with pytest.raises(ValueError):forecast_consensus_history(pd.concat([f,f],ignore_index=True))


def test_frozen_forecast_roundtrip_no_score_change_and_tamper_rejected():
    from nba_consensus_history import freeze_consensus_history
    f=fixture().assign(projected_minutes=22,projected_fd_points=22)
    saved=freeze_consensus_history(f)
    pd.testing.assert_frame_equal(saved[f.columns],f)
    assert saved.shadow_ch_consensus_history_fd.iloc[0]==31.875
    assert compare_consensus_history(saved,require_frozen=True)['Paired players'].tolist()==[1,1,1]
    assert compare_consensus_history(f,require_frozen=True)['Paired players'].tolist()==[0,0,0]
    changed=saved.assign(shadow_ch_consensus_history_fd=99.)
    assert compare_consensus_history(changed,require_frozen=True)['Paired players'].tolist()==[0,0,0]
    changed=saved.assign(shadow_consensus_history_as_of='2026-11-27T20:01:00Z')
    assert compare_consensus_history(changed,require_frozen=True)['Paired players'].tolist()==[0,0,0]

def test_freeze_uses_daily_fantasy_not_box_score_points():
    from nba_consensus_history import freeze_consensus_history
    f=fixture().assign(projected_minutes=22,projected_fd_points=22,daily_points=999)
    saved=freeze_consensus_history(f)
    assert saved.daily_points.iloc[0]==999
    assert saved.shadow_ch_consensus_history_fd.iloc[0]==31.875

def test_post_tip_freeze_leaves_input_unmodified():
    from nba_consensus_history import freeze_consensus_history,FROZEN_FIELDS
    f=fixture().assign(projected_minutes=22,projected_fd_points=22,
                       replay_before_full_slate_tip=False)
    pd.testing.assert_frame_equal(freeze_consensus_history(f),f)
    assert not set(FROZEN_FIELDS)&set(f)

def test_capture_and_replay_roundtrip_frozen_predictions():
    from datetime import date
    from io import StringIO
    from slate_replay_capture import capture_pool,build_replay_rows
    f=fixture().assign(projected_minutes=22,projected_fd_points=22,
                       fanduel_name='Player')
    evidence=pd.DataFrame(json.loads(f.replay_evidence_json.iloc[0])).assign(
        fanduel_id='137200-1',review='Reviewed',status='',starter='',role='')
    schedule=[dict(awayTeam={'teamTricode':'BOS'},homeTeam={'teamTricode':'NYK'},gameTimeUtc=TIP)]
    saved=capture_pool(f,evidence,schedule,date(2026,11,27),CAP,('a'*64,'b'*64))
    saved=pd.read_csv(StringIO(saved.to_csv(index=False)))
    results=pd.DataFrame([dict(fanduel_id='137200-1',outcome='Played',
        nba_actual_minutes=30,nba_fd_points=36,nba_source='official',recorded_fd_points=36)])
    replay=build_replay_rows(saved.drop(columns=['daily_points','daily_minutes','actual_points','actual_minutes','verified_outcome','nba_source']),results,date(2026,11,27))
    assert compare_consensus_history(replay,require_frozen=True)['Paired players'].tolist()==[1,1,1]
