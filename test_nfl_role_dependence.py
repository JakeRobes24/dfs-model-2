import pandas as pd
import pytest

from nfl_role_dependence import SCORE_WEIGHTS, compare_frozen_role_dependence, offensive_history, prior_game_forecasts


def test_offensive_score_requires_authoritative_volume_and_includes_yardage_bonus():
    row = dict(gsis_id='id', team='DET', opponent='CHI', game_id='exact', week=1,
               position='QB', carries=2, targets=0, rushing_yards=20, receiving_yards=0)
    fields = {name: 0 for name in SCORE_WEIGHTS}
    fields.update(passing_yards=300, passing_tds=2, passing_interceptions=1)
    weekly = pd.DataFrame([{**fields, **row, 'season': 2026, 'season_type': 'REG'}]).rename(
        columns={'gsis_id': 'player_id', 'opponent': 'opponent_team'})
    workload = pd.DataFrame([row])
    assert offensive_history(workload, weekly, season=2026).actual.tolist() == [24.]
    assert offensive_history(workload, weekly.assign(carries=3), season=2026).empty
    duplicate = pd.concat([weekly, weekly.assign(position='RB')])
    assert offensive_history(workload, duplicate, season=2026).empty


def test_complete_earlier_team_games_required_and_target_score_excluded_from_forecast():
    history = pd.DataFrame([dict(team='DET', gsis_id='q', team_game_number=i, position='QB',
                                 gameday=f'2026-09-{i+1:02}', actual=float(i)) for i in range(5)])
    assert prior_game_forecasts(history).forecast.tolist() == [1.5]
    history.loc[4, 'actual'] = 50
    assert prior_game_forecasts(history).forecast.tolist() == [1.5]
    assert prior_game_forecasts(history.drop(1)).empty


def test_frozen_cv_uses_earlier_season_and_does_not_change_pair_support():
    games = []
    for n in range(6):
        for team in ['DET', 'CHI']:
            for position in ['QB', 'WR']:
                games.append(dict(game_id=f'g{n}', gameday=f'2025-09-{n+1:02}', gsis_id=team+position,
                                  team=team, week=1, position=position, forecast=18., actual=18.+n,
                                  residual=float(n)))
    training = pd.DataFrame(games)
    test = training.assign(gameday='2026-09-25')
    report = compare_frozen_role_dependence(training, test, minimum_games=2)
    pair = report.loc[report.pair.eq('Same-team QB–WR')]
    assert pair.groupby('policy').size().to_dict() == {'Frozen role dependence': 12, 'Independent': 12}
    assert pair.loc[pair.policy.eq('Frozen role dependence')].correlation.gt(0).all()
    test['residual'] = -test.residual
    pd.testing.assert_frame_equal(report, compare_frozen_role_dependence(training, test, minimum_games=2))
    with pytest.raises(ValueError, match='before evaluation'):
        compare_frozen_role_dependence(test, training, minimum_games=2)
