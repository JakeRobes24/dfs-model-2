import pandas as pd
from nba_research_triage import disagreement_queue


def test_disagreement_queue_distinguishes_consensus_conflict_and_missing():
    pool = pd.DataFrame({
        'fanduel_id': list('abcdef'), 'fanduel_name': list('ABCDEF'),
        'eligible': [True, True, True, True, False, True], 'salary': 5000,
        'projected_fd_points': 30, 'adjusted_fd_points': [30,30,30,0,30,30],
        'independent_fd_points': [42,42,38,None,50,31],
        'projection_source_count': [2,2,1,0,2,2],
        'projection_source_spread': [2,9,0,None,1,1],
        'projected_minutes': 25, 'independent_minutes': [32,25,25,None,25,25],
        'recent_mpg': [32,25,25,None,25,25], 'blend_status': 'unchanged',
    })
    original = pool.copy(deep=True)
    queue = disagreement_queue(pool)
    assert queue.fanduel_id.tolist() == ['d','a','b','c']
    reasons = queue.set_index('fanduel_id').review_reason
    assert 'Agreeing providers differ from DAILY' in reasons.a
    assert 'Independent minutes differ' in reasons.a
    assert 'Recent rotation differs' in reasons.a
    assert 'providers conflict' in reasons.b
    assert 'Agreeing providers' not in reasons.b
    assert 'Single-source' in reasons.c
    assert 'Missing usable' in reasons.d
    pd.testing.assert_frame_equal(pool, original)
    assert disagreement_queue(pool.iloc[0:0]).empty


def test_paired_gap_decomposition_never_borrows_other_provider_minutes():
    import json
    import pytest
    from nba_research_triage import paired_gap_breakdown

    def evaluate(*notes):
        return paired_gap_breakdown(30, 30, json.dumps(notes))

    minutes_only = dict(family='a', points=40, paired_minutes=40, weight=1)
    rate_only = dict(family='b', points=45, paired_minutes=30, weight=.5)
    unpaired = dict(family='c', points=90, weight=1)
    one = evaluate(minutes_only, unpaired)
    assert one['paired_source_count'] == 1
    assert one['time_effect'] == 10
    assert one['rate_effect'] == 0
    assert one['paired_gap_driver'] == 'Mainly projected minutes'
    two = evaluate(rate_only)
    assert two['time_effect'] == 0 and two['rate_effect'] == 15
    assert two['paired_gap_driver'] == 'Mainly projected production rate'
    both = evaluate(minutes_only, rate_only, unpaired)
    assert both['paired_source_count'] == 2
    assert both['paired_point_gap'] == pytest.approx(17.5 / 1.5)
    assert both['time_effect'] + both['rate_effect'] == pytest.approx(both['paired_point_gap'])
    assert evaluate(unpaired)['paired_gap_driver'] == 'Paired evidence unavailable'
    assert evaluate(minutes_only, minutes_only)['paired_source_count'] == 0
    offset = evaluate(dict(family='a', points=30, paired_minutes=40, weight=1))
    assert offset['paired_gap_driver'] == 'Offsetting time and rate effects'
    assert offset['time_effect'] + offset['rate_effect'] == pytest.approx(0)
