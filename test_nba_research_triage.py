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
