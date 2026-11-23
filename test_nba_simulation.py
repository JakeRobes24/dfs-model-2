import numpy as np
import pandas as pd
import pytest

from nba_simulation import OutcomeDraws, simulate_nba, walk_forward_ranges


def historical_rows(day, minutes_offset):
    count = 24
    return pd.DataFrame({
        'slate_date': day, 'fanduel_id': [f'{day}-{i}' for i in range(count)],
        'eligible': True, 'daily_minutes': 25, 'daily_points': 28,
        'actual_minutes': np.linspace(15, 35, count) + minutes_offset,
        'actual_points': np.linspace(12, 58, count),
    })


def test_simulation_reproducible_and_ignores_same_day_data():
    prior = historical_rows('2026-11-18', 0)
    same_day = historical_rows('2026-11-20', 12)
    pool = pd.DataFrame({'fanduel_id': ['p'], 'projected_minutes': [20], 'projected_fd_points': [30]})
    first = simulate_nba(prior, pool, '2026-11-20', draws=256)
    second = simulate_nba(pd.concat([same_day, prior]), pool, '2026-11-20', draws=256)
    np.testing.assert_array_equal(first.fd_points, second.fd_points)
    np.testing.assert_array_equal(first.minutes, second.minutes)
    assert first.player_ranges().loc[0, 'fd_p90'] > first.player_ranges().loc[0, 'fd_p10']
    with pytest.raises(ValueError, match='Insufficient earlier'):
        simulate_nba(same_day, pool, '2026-11-20')


def test_lineup_ranges_sum_shared_draws_and_reject_invalid_membership():
    history = historical_rows('2026-11-18', 0)
    ids = [f'p{i}' for i in range(10)]
    pool = pd.DataFrame({'fanduel_id': ids, 'projected_minutes': 20, 'projected_fd_points': 30})
    outcomes = simulate_nba(history, pool, '2026-11-20', draws=256)
    roster = pd.DataFrame({'lineup': 1, 'fanduel_id': ids[:9]})
    expected = np.quantile(outcomes.fd_points[:, :9].sum(axis=1), .9)
    assert outcomes.lineup_ranges(roster).loc[0, 'fd_p90'] == pytest.approx(expected)
    with pytest.raises(ValueError, match='nine distinct'):
        outcomes.lineup_ranges(pd.concat([roster.iloc[:8], roster.iloc[[0]]]))
    with pytest.raises(ValueError, match='no simulated outcomes'):
        outcomes.lineup_ranges(roster.replace({'p8': 'missing'}))


def test_walk_forward_scores_only_later_played_records():
    prior = historical_rows('2026-11-18', 0)
    test = historical_rows('2026-11-20', 12)
    test.loc[0, 'actual_minutes'] = 0
    test.loc[0, 'actual_points'] = 0
    report = walk_forward_ranges(pd.concat([prior, test]), draws=256).iloc[0]
    assert report.slate_date == '2026-11-20'
    assert report.training_players == 24
    assert report.test_players == 23
    assert report.minutes_80pct_coverage < 0.8


def test_lineup_comparisons_cancel_shared_players_and_keep_ties():
    ids = pd.Index([f'p{i}' for i in range(10)])
    scores = np.full((3, 10), 25.0)
    scores[:, 8] = [10, 20, 30]
    scores[:, 9] = [30, 20, 20]
    outcomes = OutcomeDraws(ids, np.zeros_like(scores), scores)
    rosters = pd.DataFrame({
        'lineup': ['A'] * 9 + ['B'] * 9 + ['A reordered'] * 9,
        'fanduel_id': list(ids[:9]) + list(ids[:8]) + [ids[9]] + list(reversed(ids[:9])),
    })
    report = outcomes.compare_lineups(rosters).set_index(['lineup', 'alternative'])
    pair = report.loc[('A', 'B')]
    assert pair.lineup_ahead_share == pair.alternative_ahead_share == pair.tie_share == 1 / 3
    assert pair.fd_gap_p10 == -16 and pair.fd_gap_p50 == 0 and pair.fd_gap_p90 == 8
    assert report.loc[('A', 'A reordered'), 'tie_share'] == 1


def test_lineup_review_requires_verified_outcomes_and_excludes_ties_from_probability_error():
    ids = pd.Index([f'p{i}' for i in range(10)])
    scores = np.full((2, 10), 25.0)
    scores[:, 8] = [26, 27]
    simulation = OutcomeDraws(ids, np.zeros_like(scores), scores)
    rosters = pd.DataFrame({'lineup': ['A'] * 9 + ['B'] * 9,
                            'fanduel_id': list(ids[:9]) + list(ids[:8]) + [ids[9]]})
    predictions = pd.DataFrame({'fanduel_id': ids, 'projected_fd_points': [25] * 9 + [26]})
    official = pd.DataFrame({'fanduel_id': ids, 'outcome': 'Played', 'nba_source': 'Official box',
                             'nba_fd_points': [25] * 9 + [24]})
    result = simulation.review_lineup_comparisons(rosters, predictions, official).iloc[0]
    assert result.actual_gap == 1 and result.projected_gap == -1
    assert result.simulation_direction_correct and not result.projection_direction_correct
    assert result.simulation_brier == 0
    official.loc[9, 'nba_fd_points'] = 25
    tied = simulation.review_lineup_comparisons(rosters, predictions, official).iloc[0]
    assert pd.isna(tied.simulation_brier)
    official.loc[9, 'outcome'] = 'Did not play'
    assert simulation.review_lineup_comparisons(rosters, predictions, official).empty
