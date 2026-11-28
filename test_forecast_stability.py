import pandas as pd
import pytest
from forecast_stability import nba_error_cohorts, nfl_week_stability


def test_nba_cohorts_and_history_cutoff():
    x = pd.DataFrame([dict(date='2026-11-24', id='a', actual=10, base=25, both=20,
                           exposure=3, base_minutes=30, history_end='2026-11-23'),
                      dict(date='2026-11-24', id='b', actual=10, base=8, both=6,
                           exposure=0, base_minutes=20, history_end='2026-11-23')])
    r = nba_error_cohorts(x).query("period == 'pooled'").set_index('cohort')
    assert r.loc['all', 'base_mae'] == 8.5
    assert r.loc['all', 'challenger_mae'] == 7
    assert r.loc['repeat3plus', 'base_large_miss'] == 1
    assert r.loc['all', 'improved'] == 1
    with pytest.raises(ValueError):
        nba_error_cohorts(x.assign(history_end='2026-11-24'))


def test_nfl_week_stability_and_missing_policy():
    rows=[]
    for w, p in [(5, .6), (6, .8)]:
        for policy, v in [('Actual scoring average', .5), ('Expected scoring average', .9), ('fixed_prior_blend', p)]:
            rows.append(dict(date=f'2026-10-{w:02}', week=w, game_id=str(w), position='WR', channel='receiving',
                             policy=policy, players=3, pairs=3, order_accuracy=v, leader_regret=1-v, leader_hit=v))
    x=pd.DataFrame(rows)
    r=nfl_week_stability(x, scope='game').set_index('metric')
    assert r.loc['order_accuracy', 'improved']==2
    assert r.loc['leader_regret', 'mean_delta']==pytest.approx(.2)
    assert r.loc['leader_hit', 'loo_min']==pytest.approx(.1)
    with pytest.raises(ValueError):
        nfl_week_stability(x.iloc[:-1], scope='game')
