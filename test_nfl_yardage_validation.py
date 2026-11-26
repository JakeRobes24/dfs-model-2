import json
from pathlib import Path

import pytest

from nfl_yardage_validation import evaluate_yardage, review_cohorts


EVIDENCE = Path(__file__).parent / 'docs/validation/nfl-yardage-evidence.json'


def test_real_yardage_replay_preserves_training_order_and_simulation_marginals():
    results = review_cohorts(json.loads(EVIDENCE.read_text())['cohorts'])
    assert [row['comparison_dates'] for row in results] == [5, 5, 13, 10, 11, 2]
    for result in results:
        for paired, independent in zip(result['simulations'][::2], result['simulations'][1::2]):
            assert paired['date'] == independent['date']
            assert len(set(paired['training_dates'])) == 4
            assert max(paired['training_dates']) < paired['date']
            assert paired['expected_pair_yards'] == pytest.approx(independent['expected_pair_yards'])
    rams_rushing = results[0]
    assert rams_rushing['point_summary'][1]['mae'] == pytest.approx(35.275)
    assert rams_rushing['simulation_summary'][1]['crps'] == pytest.approx(40.2484375)


def test_missing_receiving_workload_cannot_skip_back_to_older_games():
    rams = json.loads(EVIDENCE.read_text())['cohorts'][0]
    history = rams['history']
    args = {key: rams[key] for key in ('player_ids', 'team', 'target_day')}
    old = evaluate_yardage(history, **args, metric='receiving')
    holdout = next(row for row in old['predictions'] if row['policy'] == 'Last-game yards')
    gap = holdout['training_dates'][-1]
    altered = [dict(row, targets={}) if row['date'] == gap else row for row in history]
    new = evaluate_yardage(altered, **args, metric='receiving')
    assert new['comparison_dates'] < old['comparison_dates']
    assert all(row['date'] != holdout['date'] for row in new['predictions'])
