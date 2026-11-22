from datetime import date
from io import StringIO
import json

import pandas as pd

from history_intake import make_submission
from prelock import REQUIRED
from slate_replay_capture import capture_pool


def test_replay_capture_round_trips_reviewed_evidence_and_fails_closed_on_timing():
    slate = date(2026, 11, 20)
    pool = pd.DataFrame({'fanduel_id': ['123-1', '123-2', '123-3'],
                         'fanduel_name': ['Guard', 'Forward', 'Center'], 'position': ['PG', 'SF', 'C'],
                         'game': ['BOS@NYK', 'SAC@GSW', 'CLE@ORL'], 'salary': [8000, 6000, 5000],
                         'adjusted_fd_points': [30, 24, 20]})
    # Include other legacy pool columns required by the immutable packet writer.
    from data_integrity import REQUIRED as POOL_FIELDS
    pool = pool.assign(**{field: '' for field in POOL_FIELDS - set(pool)})
    evidence = {field: '' for field in REQUIRED}
    audit = pd.DataFrame([
        dict(evidence, fanduel_id='123-1', source='NBA injury report', status='questionable',
             official=True, observed_at='2026-11-20T23:00:00Z', review='Reviewed'),
        dict(evidence, fanduel_id='123-1', source='Later report', status='out',
             official=True, observed_at='2026-11-21T00:00:00Z', review='Reviewed'),
        dict(evidence, fanduel_id='123-1', source='Rejected source',
             observed_at='2026-11-20T22:00:00Z', review='Stale'),
    ])
    schedule = [
        dict(awayTeam={'teamTricode': 'BOS'}, homeTeam={'teamTricode': 'NYK'},
             gameTimeUtc='2026-11-21T00:00:00Z'),
        dict(awayTeam={'teamTricode': 'SAC'}, homeTeam={'teamTricode': 'GSW'},
             gameTimeUtc='2026-11-21T03:00:00Z', actualStartTimeUTC='2026-11-20T23:15:00Z'),
    ]
    captured = capture_pool(pool, audit, schedule, slate, '2026-11-20T23:30:00Z', ('a' * 64, 'b' * 64))
    assert captured.replay_timing.tolist() == ['before_scheduled_tip', 'at_or_after_cutoff', 'schedule_unverified']
    assert not captured.replay_before_full_slate_tip.any()
    assert captured.replay_daily_sha256.eq('b' * 64).all()
    assert captured.replay_evidence_json.iloc[1] == '[]'
    pd.testing.assert_frame_equal(captured[pool.columns], pool)
    _, packet = make_submission(captured, slate)
    parsed = pd.read_csv(StringIO(json.loads(packet)['research_csv']))
    saved = json.loads(parsed.replay_evidence_json.iloc[0])
    assert [row['source'] for row in saved] == ['NBA injury report']
    qualified = capture_pool(pool.iloc[:1], audit, schedule, slate, '2026-11-20T23:30:00Z', ('a', 'b'))
    assert qualified.replay_before_full_slate_tip.all()
    duplicate = capture_pool(pool.iloc[:1], audit, schedule + [schedule[0]], slate, '2026-11-20T23:30:00Z', ('a', 'b'))
    assert duplicate.replay_timing.iloc[0] == 'schedule_unverified'


def test_replay_export_rechecks_saved_timing_and_preserves_unresolved_results():
    import pytest

    from slate_replay_capture import build_replay_rows

    day = date(2026, 11, 20)
    pool = pd.DataFrame({'fanduel_id': ['123-1', '123-2', '123-3'], 'fanduel_name': ['A', 'B', 'C'],
                         'team': 'BOS', 'game': 'BOS@NYK', 'eligible': True,
                         'prelock_status': '', 'prelock_starter': '', 'projected_minutes': 21,
                         'projected_fd_points': 24, 'adjusted_minutes': 22, 'adjusted_fd_points': 25})
    schedule = [dict(awayTeam={'teamTricode': 'BOS'}, homeTeam={'teamTricode': 'NYK'},
                     gameTimeUtc='2026-11-21T00:00:00Z')]
    quotes = [dict(description='A', name=side, point=18.5, price=1.9) for side in ('Over', 'Under')]
    market_events = [dict(
        away_team='Boston Celtics', home_team='New York Knicks', commence_time='2026-11-21T00:00:00Z',
        bookmakers=[
            dict(key=key, last_update=stamp, markets=[dict(key='player_points', outcomes=quotes)])
            for key, stamp in [('fresh', '2026-11-20T22:55:00Z'), ('future', '2026-11-20T23:05:00Z'),
                               ('stale', '2026-11-20T20:55:00Z')]
        ])]
    saved = capture_pool(pool.assign(daily_points=21), pd.DataFrame(), schedule, day, '2026-11-20T23:00:00Z',
                         ('a' * 64, 'b' * 64), market_events=market_events)
    results = pd.DataFrame({'fanduel_id': ['123-1', '123-2'], 'outcome': ['Played', 'Did not play'],
                            'nba_actual_minutes': [24, None], 'nba_fd_points': [31, None],
                            'nba_source': ['NBA box', 'NBA final game roster'],
                            'recorded_fd_points': [29, None]})
    export = build_replay_rows(saved, results, day)
    pd.testing.assert_frame_equal(export, build_replay_rows(
        saved.astype({'replay_before_full_slate_tip': str, 'eligible': str}), results, day))
    assert export.verified_outcome.tolist() == ['played', 'did_not_play', 'needs_review']
    assert export.eligible.all()
    assert export.loc[0, 'actual_points'] == 31 and export.loc[0, 'recorded_fd_points'] == 29
    assert export.loc[[1, 2], 'actual_points'].isna().all()
    props = json.loads(export.loc[0, 'replay_player_props_json'])
    assert len(props) == 1 and props[0]['bookmaker'] == 'fresh'
    assert props[0]['daily_stat'] == 21 and props[0]['daily_minus_line'] == 2.5
    assert props[0]['source'] == 'The Odds API snapshot'
    assert export.loc[1, 'replay_player_props_json'] == '[]'
    early_tip = [dict(schedule[0], actualStartTimeUTC='2026-11-20T22:59:00Z')]
    already_started = capture_pool(pool, pd.DataFrame(), early_tip, day, '2026-11-20T23:00:00Z',
                                   ('a' * 64, 'b' * 64), market_events=market_events)
    assert 'replay_player_props_json' not in already_started
    with pytest.raises(ValueError, match='predates'):
        build_replay_rows(pool, results, day)
    with pytest.raises(ValueError, match='before every game'):
        build_replay_rows(saved.assign(replay_captured_at_utc='2026-11-21T00:00:00Z'), results, day)
