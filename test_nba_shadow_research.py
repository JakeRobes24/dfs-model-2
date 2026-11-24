from datetime import date

import pandas as pd
import pytest

from nba_shadow_research import FEATURES, freeze_research_features, compare_shadow_forecasts
from slate_replay_capture import capture_pool, build_replay_rows


def test_frozen_research_comparison_uses_same_rows_and_preserves_scores():
    day = date(2026, 11, 20)
    pool = pd.DataFrame({'fanduel_id': ['123-1','123-2','123-3'], 'fanduel_name': ['A','B','C'],
                         'team': 'BOS', 'game': 'BOS@NYK', 'eligible': True,
                         'prelock_status': '', 'prelock_starter': ['starter','bench',''],
                         'projected_minutes': 30, 'adjusted_minutes': 30,
                         'projected_fd_points': 30, 'adjusted_fd_points': 30})
    summaries = pd.DataFrame({'fanduel_id': pool.fanduel_id,
        'FD points per minute': [2,2,2], 'Games with complete FD stats': [3,1,3],
        'Minutes with complete FD stats': [90,30,90], 'Box-score sources': 'NBA box',
        'FD/min as starter': 2, 'FD/min off bench': 2,
        'Starter complete FD games': 3, 'Bench complete FD games': 3,
        'Starter complete FD minutes': 90, 'Bench complete FD minutes': 90})
    splits = pd.DataFrame({'fanduel_id': ['123-1','123-2','123-2'],
        'FD rate evidence': 'Observed comparison', 'FD/min without': 2,
        'Complete FD games without': 3, 'Complete FD minutes without': 90,
        'Out teammate': ['X','Y','Z']})
    match = pd.DataFrame({'fanduel_id': pool.fanduel_id, 'team_pace48': 100,
        'descriptive_pace_mean': 110, 'team_games': 3, 'opponent_games': [3,1,3],
        'opponent_def_rating': 120, 'team_sources': 'NBA box', 'opponent_sources': 'NBA box'})
    frozen = freeze_research_features(pool, summaries, splits, match)
    pd.testing.assert_frame_equal(frozen[pool.columns], pool)
    assert pd.isna(frozen.loc[1, 'shadow_absence_fppm'])
    assert pd.isna(frozen.loc[2, 'shadow_role_fppm'])
    schedule = [dict(awayTeam={'teamTricode':'BOS'},homeTeam={'teamTricode':'NYK'},
                     gameTimeUtc='2026-11-20T23:00:00Z')]
    capture = capture_pool(frozen, pd.DataFrame(), schedule, day, '2026-11-20T22:00:00Z',
                           ('a'*64,'b'*64))
    outcomes = pd.DataFrame({'fanduel_id': pool.fanduel_id,
        'outcome': ['Played','Played','Did not play'], 'nba_actual_minutes': [30,30,None],
        'nba_fd_points': [36,40,None], 'nba_source': 'NBA box', 'recorded_fd_points': None})
    replay = build_replay_rows(capture, outcomes, day)
    assert set(FEATURES) <= set(replay)
    report = compare_shadow_forecasts(replay).set_index('Policy')
    assert report.loc['Recent rate', 'Paired players'] == 1
    assert report.loc['Recent rate', 'Reviewed MAE'] == 6
    assert report.loc['Recent rate', 'Shadow MAE'] == 0
    assert report.loc['Confirmed role rate', 'Paired players'] == 2
    assert report.loc['Single OUT teammate rate', 'Paired players'] == 1
    assert report.loc['Pace', 'Shadow MAE'] == pytest.approx(4.5)
    assert report.loc['Recent rate + pace', 'Shadow MAE'] == pytest.approx(1.8)
    assert compare_shadow_forecasts(replay.drop(columns=list(FEATURES))).empty
