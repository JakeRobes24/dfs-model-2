import json
from pathlib import Path

import pytest

from nfl_yardage_validation import evaluate_yardage, review_cohorts, empirical_crps


def test_sorted_crps_matches_pairwise_formula_and_scales_to_large_draws():
    import numpy as np
    rng = np.random.default_rng(2026)
    for draws in ([0.], [0., 0., 3., -1.], rng.normal(size=256)):
        x = np.asarray(draws)
        for actual in (-2., 0., 5.):
            old = np.abs(x-actual).mean() - .5*np.abs(x[:,None]-x).mean()
            assert empirical_crps(x, actual) == pytest.approx(old, abs=1e-12)
    assert empirical_crps(np.zeros(100_000), 5.) == pytest.approx(5.)
    for bad in ([], [float('nan')], [[1.,2.]]):
        with pytest.raises(ValueError):
            empirical_crps(bad, 1.)


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


def test_receiving_share_blend_on_archived_cohorts():
    from nfl_history_baseline_review import compare_receiving_baselines
    for cohort, expected_count, expected_mae in zip(
            json.loads(EVIDENCE.read_text())['cohorts'], (5,10,2),
            (2.270230394390309,1.7029984440291852,1.200435222672065)):
        args = {key: cohort[key] for key in ('player_ids','team','target_day')}
        result = compare_receiving_baselines(cohort['history'], **args, share_blend_challenge=True)
        assert {row['dates'] for row in result['summary']} == {expected_count}
        assert result['summary'][-1]['mae'] == pytest.approx(expected_mae)
        from collections import defaultdict
        by_date = defaultdict(dict)
        for row in result['rows']:
            by_date[row['date']][row['policy']] = row['estimated_targets']
            assert max(row['training_dates']) < row['date']
        for p in by_date.values():
            assert p['blended direct targets and recent shares'] == pytest.approx([
                (a+b)/2 for a,b in zip(p['four-game targets'],p['four-game volume + recent shares'])])


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


def test_mixed_dependence_on_archived_backfields():
    results=review_cohorts(json.loads(EVIDENCE.read_text())['cohorts'],mixed_dependence=True)
    expected=(42.004296875,18.36015625,40.31700721153846,24.36875,43.62979403409091,8.634765625)
    for result,score in zip(results,expected):
        assert result['simulation_summary'][-1]['policy']=='Half paired half independent'
        assert result['simulation_summary'][-1]['crps']==pytest.approx(score)
        for i in range(0,len(result['simulations']),3):
            group=result['simulations'][i:i+3]
            assert len({r['date'] for r in group})==1
            assert [r['expected_pair_yards'] for r in group]==pytest.approx([group[0]['expected_pair_yards']]*3)
