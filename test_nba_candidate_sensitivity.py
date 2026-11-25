import numpy as np
import pandas as pd
import pytest
from nba_simulation import OutcomeDraws
from nba_candidate_sensitivity import SCENARIOS, correlated_draws, candidate_sensitivity


def setup():
    rng = np.random.default_rng(3)
    ids = pd.Index([f'p{i}' for i in range(12)])
    points = rng.normal(30, 8, (4000,12))
    minutes = points / 2 + rng.normal(15,1,(4000,12))
    draws = OutcomeDraws(ids, minutes, points)
    pool = pd.DataFrame({'fanduel_id': ids, 'team': ['BOS']*3+['NYK']*3+['CLE']*3+['ORL']*3,
                         'game': ['BOS@NYK']*6+['CLE@ORL']*6})
    rosters = pd.DataFrame({'lineup': ['A']*9+['B']*9,
                            'fanduel_id': list(ids[:9])+list(ids[3:])})
    return draws,pool,rosters


def test_sensitivity_preserves_paired_player_marginals_and_varies_dependence():
    draws,pool,_ = setup()
    for scenario in SCENARIOS:
        result = correlated_draws(draws,pool,scenario)
        for i in range(len(draws.fanduel_ids)):
            old = np.argsort(draws.fd_points[:,i])
            new = np.argsort(result.fd_points[:,i])
            np.testing.assert_array_equal(draws.fd_points[old,i],result.fd_points[new,i])
            np.testing.assert_array_equal(draws.minutes[old,i],result.minutes[new,i])
        np.testing.assert_array_equal(result.fd_points,correlated_draws(draws,pool,scenario).fd_points)
    positive = correlated_draws(draws,pool,'Shared game and team')
    opposing = correlated_draws(draws,pool,'Opposing game and shared team')
    corr = np.corrcoef(positive.fd_points.T)
    assert corr[0,1] > .12 and corr[0,3] > .04
    assert abs(corr[0,7]) < .06
    assert np.corrcoef(opposing.fd_points.T)[0,3] < -.04


def test_portfolio_ceiling_and_tie_shares_are_not_field_probabilities():
    draws,pool,rosters = setup()
    lineups,portfolios = candidate_sensitivity(draws,pool,rosters)
    assert len(lineups)==6 and len(portfolios)==3
    np.testing.assert_allclose(lineups.groupby('Scenario')['Best among supplied candidates share'].sum(),1)
    assert (lineups.P99 >= lineups.P95).all()
    for scenario,group in lineups.groupby('Scenario'):
        assert portfolios.loc[portfolios.Scenario.eq(scenario),'Best candidate P95'].iloc[0] >= group.P95.max()
    identical = pd.concat([rosters.iloc[:9],rosters.iloc[:9].assign(lineup='same')])
    tied,_ = candidate_sensitivity(draws,pool,identical)
    assert tied['Best among supplied candidates share'].eq(.5).all()
    with pytest.raises(ValueError):
        correlated_draws(draws,pool.assign(team='BAD'),'Shared game and team')
