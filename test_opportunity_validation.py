import pandas as pd

from opportunity_validation import compare_opportunity, compare_opportunity_by_minutes


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


def test_rotation_replay_counts_wins_ties_and_losses_on_verified_scores():
    ids = ['closer', 'farther', 'tied', 'missing']
    outcomes = pd.DataFrame({
        'fanduel_id': ids, 'daily_minutes': 20, 'daily_points': 20,
        'actual_minutes': 24, 'actual_points': [30, 15, 22.5, None],
    })
    rotations = pd.DataFrame({'fanduel_id': ids, 'Last 5 minutes': 40, 'Last 10 minutes': None})
    report = compare_opportunity(outcomes, rotations, pd.DataFrame()).set_index('scenario')
    row = report.loc['DAILY plus 25% last five']
    assert row.n == 4
    assert row.n_fd_points == 3
    assert (row.fd_closer, row.fd_tied, row.fd_farther) == (1, 1, 1)
    assert row.median_fd_error_reduction == 0


def test_minutes_bands_use_the_frozen_forecast_and_keep_identical_pairs():
    ids = ['short', 'rotation', 'heavy']
    outcomes = pd.DataFrame({'fanduel_id': ids, 'daily_minutes': [17, 18, 28],
                             'daily_points': [17, 18, 28], 'actual_minutes': [30, 10, 24],
                             'actual_points': [30, 10, 24]})
    rotations = pd.DataFrame({'fanduel_id': ids, 'Last 5 minutes': [25, 22, 20], 'Last 10 minutes': None})
    report = compare_opportunity_by_minutes(outcomes, rotations, pd.DataFrame())
    paired = report.loc[report.scenario.eq('DAILY plus 25% last five')]
    assert paired.projected_minutes_band.tolist() == ['Under 18', '18 to under 28', '28 or more']
    assert paired.n_fd_points.tolist() == [1, 1, 1]
    assert paired.daily_fd_mae.tolist() == [13, 8, 4]
    assert paired.scenario_fd_mae.tolist() == [11, 9, 2]
