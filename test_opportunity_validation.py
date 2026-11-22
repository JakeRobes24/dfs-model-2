import pandas as pd

from opportunity_validation import compare_opportunity


def test_rotation_replay_scores_identical_rows_and_excludes_dnp():
    outcomes = pd.DataFrame({
        'fanduel_id': ['played', 'dnp', 'no_rotation'],
        'daily_minutes': [20, 20, 20], 'daily_points': [30, 30, 30],
        'actual_minutes': [30, 0, 30], 'actual_points': [45, 0, 45],
    })
    rotations = pd.DataFrame({
        'fanduel_id': ['played', 'dnp'], 'Last 5 minutes': [28, 28],
        'Last 10 minutes': [None, None],
    })
    report = compare_opportunity(outcomes, rotations, pd.DataFrame()).set_index('scenario')
    row = report.loc['DAILY plus 25% last five']
    assert row.played_with_baseline == 2
    assert row.n == 1
    assert row.daily_minutes_mae == 10
    assert row.scenario_minutes_mae == 8
    assert row.daily_fd_mae == 15
    assert row.scenario_fd_mae == 12
