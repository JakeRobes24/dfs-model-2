import pytest

from nba_history_roster_ranges import POLICIES
from nba_multislate_range_audit import summarize_archived_dates


def evaluation(actuals):
    rows = [dict(policy=policy, lineup=str(index), actual=actual, reviewed=200,
                 fd_p10=180, fd_p50=200, fd_p90=220,
                 interval_score=40 + 10 * max(180 - actual, 0, actual - 220))
            for policy in POLICIES for index, actual in enumerate(actuals)]
    return dict(lineups=rows, pairs=[])


def test_dates_contribute_equally_and_boundary_is_covered():
    result = summarize_archived_dates({
        '2026-11-22': evaluation([180]),
        '2026-11-24': evaluation([170, 221, 225]),
        '2026-11-27': evaluation([]),
    })
    score = result['equal_date']['point_residual']
    assert score['dates'] == 2
    assert (score['rosters'], score['inside'], score['below'], score['above']) == (4, 1, 1, 2)
    assert score['coverage'] == .5
    assert score['interval_score'] == pytest.approx((40 + (140 + 50 + 90) / 3) / 2)
    assert score['order_brier'] is None


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'changed_actual', 'changed_center'])
def test_reject_inconsistent_roster_pairs(change):
    result = evaluation([181])
    if change == 'missing':
        result['lineups'].pop()
    elif change == 'duplicate':
        result['lineups'].append(dict(result['lineups'][-1]))
    else:
        field = 'actual' if change == 'changed_actual' else 'reviewed'
        result['lineups'][-1][field] += 1
    with pytest.raises(ValueError):
        summarize_archived_dates({'2026-11-24': result})


def test_reject_pairwise_outcomes_that_disagree_between_policies():
    result = evaluation([181, 183])
    result['pairs'] = [
        dict(policy=policy, lineup='0', alternative='1', actual_gap=-2, reviewed_gap=0, brier=.2)
        for policy in POLICIES
    ]
    result['pairs'][1]['actual_gap'] = 2
    with pytest.raises(ValueError, match='identical lineups and outcomes'):
        summarize_archived_dates({'2026-11-24': result})
