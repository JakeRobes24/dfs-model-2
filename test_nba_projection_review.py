import pandas as pd
import pytest

from nba_projection_review import compare_frozen_projections


def test_error_comparison_uses_identical_rows_and_counts_only_verified_dnps_as_zero():
    replay = pd.DataFrame({
        'fanduel_id': ['1', '2', '3', '4', '5', '6'],
        'eligible': [True, True, True, True, True, False],
        'verified_outcome': ['played', 'did_not_play', 'needs_review', 'played', 'played', 'played'],
        'daily_points': [20, 10, 20, 24, 12, 20],
        'adjusted_fd_points': [25, 10, 100, None, 12, 999],
        'actual_points': [24, None, None, 24, 12, 20],
        'daily_minutes': [20, 10, 25, 20, 18, 20],
        'adjusted_minutes': [22, 10, 25, None, 18, 70],
        'actual_minutes': [21, None, None, 20, 19, 20],
    })
    result = compare_frozen_projections(replay).set_index(['Metric', 'Sample'])
    points = result.loc[('FanDuel points', 'All paired players')]
    assert points['Paired players'] == 3
    assert points['Eligible with verified outcome'] == 4
    assert points['DAILY MAE'] == pytest.approx(14 / 3)
    assert points['Adjusted MAE'] == pytest.approx(11 / 3)
    changed = result.loc[('FanDuel points', 'Changed projections')]
    assert changed['Paired players'] == 1 and changed['MAE improvement'] == 3
    minutes = result.loc[('Minutes', 'All paired players')]
    assert minutes['Paired players'] == 2
    assert minutes['DAILY MAE'] == minutes['Adjusted MAE'] == 1
