from collections import Counter

import pytest

from nba_rate_distribution import compare_rate_distributions, calibrate_rate_ranges, score_draws
from test_nba_history_windows import sample


def test_same_support_and_centering():
    r=compare_rate_distributions(sample(),cutoff_day='2026-11-26')
    assert not r['certified']
    assert set(Counter(x['policy'] for x in r['rows'] if x['cohort']==8).values())=={6}
    assert set(Counter(x['policy'] for x in r['rows'] if x['cohort']==12).values())=={2}
    for n in (8,12):
        p={x['policy']:x for x in r['summary'] if x['cohort']==n}
        assert p['paired']['mean_abs_error']==pytest.approx(p['independent_centered']['mean_abs_error'])
        assert p['paired']['bias']==pytest.approx(p['independent_centered']['bias'])
    rows=sample()
    rows[7].pop('assists')
    assert not compare_rate_distributions(rows,cutoff_day='2026-11-26')['rows']


def test_scores_known_distribution():
    assert score_draws([2,4],3)['crps']==pytest.approx(.5)
    assert score_draws([2,4],3)['coverage']==1
    assert score_draws([2,4],5)['upper_miss']==1


def test_calibration_uses_prior_dates_only():
    rows=[dict(cohort=8,policy='paired',date='2026-11-01',lower_excess=5.,upper_excess=-15.,width=10.),
          dict(cohort=8,policy='paired',date='2026-11-02',lower_excess=3.,upper_excess=-13.,width=10.)]
    report={r['method']:r for r in calibrate_rate_ranges(rows,minimum_prior_rows=1)}
    assert report['earlier_date']['width']==20
    assert report['earlier_date']['coverage']==1
    assert report['original']['coverage']==0
    assert report['original']['interval_score']==40
    # Same-date outcomes are excluded from the training set.
    rows[1]['date']=rows[0]['date']
    assert not calibrate_rate_ranges(rows,minimum_prior_rows=1)
