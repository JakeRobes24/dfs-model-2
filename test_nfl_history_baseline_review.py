import math
import json
from pathlib import Path
import pytest
from nfl_history_baseline_review import compare_history_baselines

def fixture():
    return json.loads((Path(__file__).parent/'docs/validation/nfl-history-baselines.json').read_text())

def run(f):
    return compare_history_baselines(f['history'],player_ids=f['player_ids'],team=f['team'],target_day=f['target_day'])

def test_archived_chronological_comparison_matches_independent_arithmetic():
    f=fixture()
    r=run(f)
    assert len(r['rows'])==15
    assert not r['certified']
    for actual,expected in zip(r['summary'],f['expected_summary']):
        assert actual['policy']==expected['policy']
        assert actual['dates']==5
        for k in ('carry_mae','volume_abs_error','share_abs_error_pp'):
            assert actual[k]==pytest.approx(expected[k])
    for row in r['rows']:
        assert len(row['training_dates'])==4
        assert all(d<row['date'] for d in row['training_dates'])

def test_future_and_same_day_excluded():
    f=fixture()
    original=run(f)
    f['history'].append(dict(f['history'][0],date='2026-11-26'))
    f['history'].append(dict(f['history'][0],date='2026-12-01'))
    assert run(f)==original

def test_heldout_actual_does_not_affect_own_prediction():
    f=fixture()
    original=run(f)
    f['history'][-1]['carries'][f['player_ids'][0]]=1
    changed=run(f)
    assert [r['predicted_carries'] for r in changed['rows']]==[r['predicted_carries'] for r in original['rows']]
    assert changed['summary']!=original['summary']

def test_duplicate_and_missing_counts_refused():
    f=fixture()
    f['history'].append(f['history'][0])
    with pytest.raises(ValueError):run(f)
    f=fixture()
    f['history'][0]['carries'].pop(f['player_ids'][0])
    with pytest.raises(ValueError):run(f)


def test_receiving_benchmark_reproduces_saved_sample():
    import json
    from pathlib import Path
    from nfl_history_baseline_review import compare_receiving_baselines
    report = json.loads((Path(__file__).parent/'docs/validation/nfl-receiving-target-benchmark.json').read_text())
    for cohort in report['cohorts']:
        result = compare_receiving_baselines(cohort['history'], player_ids=cohort['player_ids'],
                                             team=cohort['team'], target_day=cohort['target_day'])
        expected = cohort['result']
        for key in ('paired_games', 'complete_games', 'dropped_windows'):
            assert result[key] == expected[key]
        assert len(result['summary']) == len(expected['summary'])
        for actual, reference in zip(result['summary'], expected['summary']):
            assert (actual['policy'], actual['dates']) == (reference['policy'], reference['dates'])
            for metric in ('mae', 'bias', 'worst_miss'):
                assert math.isclose(actual[metric], reference[metric], rel_tol=1e-12, abs_tol=1e-12)
        for row in result['rows']:
            assert max(row['training_dates']) < row['date']
