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
    pd.testing.assert_frame_equal(captured[pool.columns], pool)
    _, packet = make_submission(captured, slate)
    parsed = pd.read_csv(StringIO(json.loads(packet)['research_csv']))
    saved = json.loads(parsed.replay_evidence_json.iloc[0])
    assert [row['source'] for row in saved] == ['NBA injury report']
    qualified = capture_pool(pool.iloc[:1], audit, schedule, slate, '2026-11-20T23:30:00Z', ('a', 'b'))
    assert qualified.replay_before_full_slate_tip.all()
    duplicate = capture_pool(pool.iloc[:1], audit, schedule + [schedule[0]], slate, '2026-11-20T23:30:00Z', ('a', 'b'))
    assert duplicate.replay_timing.iloc[0] == 'schedule_unverified'
