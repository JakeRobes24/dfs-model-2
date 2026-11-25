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
