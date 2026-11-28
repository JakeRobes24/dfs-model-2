"""Deterministic concurrency and accounting checks; no live network required."""
from threading import Barrier
import pytest

from nba_research_acquisition import acquire_research


def test_all_three_batches_start_concurrently_and_keep_results_separate():
    gate = Barrier(3, timeout=5)
    def load(value):
        def run():
            gate.wait()
            return value
        return run
    public, rotations, refs, timing = acquire_research(
        load((['injury'], ['projection'], ['status'])),
        load((['box score'], 'rotation status')),
        load(({'MatchWiz': []}, {'KeelStats': 'Unavailable'})))
    assert public == (['injury'], ['projection'], ['status'])
    assert rotations == (['box score'], 'rotation status')
    assert refs == ({'MatchWiz': []}, {'KeelStats': 'Unavailable'})
    assert len(timing['tasks']) == 3
    assert all(0 <= t <= timing['elapsed_seconds'] for t in timing['tasks'].values())


def test_reference_refresh_can_be_omitted_without_reducing_other_research():
    gate = Barrier(2, timeout=5)
    def first():
        gate.wait()
        return 'public'
    def second():
        gate.wait()
        return 'rotations'
    public, rotations, refs, timing = acquire_research(first, second)
    assert (public, rotations, refs) == ('public', 'rotations', None)
    assert len(timing['tasks']) == 2


def test_unexpected_loader_failure_remains_visible():
    def fail():
        raise RuntimeError('unexpected test error')
    with pytest.raises(RuntimeError, match='unexpected test error'):
        acquire_research(fail, lambda: 'rotations', lambda: 'references')


def test_extended_history_requires_all_tips_and_ninety_minute_buffer():
    from datetime import date
    from nba_research_acquisition import extended_history_safe
    slate=date(2026,11,28)
    now='2026-11-28T20:00:00Z'
    def entry(away,home,tip,**extra):
        return dict(dict(awayTeam={'teamTricode':away},homeTeam={'teamTricode':home},
                         gameTimeUtc=tip,gameStatus=1),**extra)
    a=entry('ORL','WSH','2026-11-28T21:30:00Z')
    b=entry('BKN','CHA','2026-11-28T23:00:00Z')
    games=['ORL@WSH','BKN@CHA']
    def allowed(rows,clock=now):
        return extended_history_safe(rows,games,clock,slate)
    assert allowed([a,b])
    assert extended_history_safe([a,b],['ORL@WAS','BRK@CHA'],now,slate)
    assert not extended_history_safe([a,b],['WSH@WAS','BKN@CHA'],now,slate)
    assert not allowed([a,b],'2026-11-28T20:00:01Z')
    assert not allowed([a])
    assert not allowed([a,b,a])
    assert not allowed([dict(a,gameStatus=2),b])
    assert not allowed([dict(a,gameStatus='3'),b])
    assert not allowed([dict(a,actualStartTimeUTC='2026-11-28T19:59:00Z'),b])
    assert not allowed([dict(a,gameTimeUtc='2026-11-28T21:30:00'),b])
    assert not allowed([a,b],'2026-11-27T20:00:00Z')
    assert not allowed([a,b],'2026-11-28T20:00:00')
    assert not extended_history_safe([a,b],games+['malformed'],now,slate)
