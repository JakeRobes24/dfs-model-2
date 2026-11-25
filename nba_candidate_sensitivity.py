"""Research-only same-game dependence sensitivity, preserving player marginals."""
import numpy as np
import pandas as pd

from nba_simulation import OutcomeDraws
from slate_import import game_code, matchup_key, team_code

# Fixed latent rank-dependence stress assumptions, not estimated correlations.
SCENARIOS = {
    'Independent': (0., 0., 1),
    'Shared game and team': (.10, .10, 1),
    'Opposing game and shared team': (.10, .10, -1),
}


def correlated_draws(outcomes, pool, scenario, *, seed=42):
    if scenario not in SCENARIOS:
        raise ValueError('Unknown dependence sensitivity scenario.')
    if not {'fanduel_id', 'game', 'team'} <= set(pool) or not pool.fanduel_id.is_unique:
        raise ValueError('Dependence sensitivity requires unique contest player and game identities.')
    target = pool.set_index('fanduel_id').reindex(outcomes.fanduel_ids)
    games = target.game.map(game_code).map(matchup_key)
    teams = target.team.map(team_code)
    if any(len(game.split('/')) != 2 or team not in game.split('/')
           for game, team in zip(games, teams)):
        raise ValueError('Every simulated player needs a verified matchup and team.')
    if scenario == 'Independent':
        return outcomes
    game_weight, team_weight, opponent_sign = SCENARIOS[scenario]
    count, players = outcomes.fd_points.shape
    rng = np.random.default_rng(seed)
    game_factors = {game: rng.standard_normal(count) for game in sorted(set(games))}
    team_factors = {key: rng.standard_normal(count) for key in sorted(set(zip(games, teams)))}
    latent = rng.standard_normal((count, players)) * np.sqrt(1 - game_weight - team_weight)
    points, minutes = np.empty_like(outcomes.fd_points), np.empty_like(outcomes.minutes)
    for i, (game, team) in enumerate(zip(games, teams)):
        sign = 1 if team == game.split('/')[0] else opponent_sign
        latent[:, i] += (np.sqrt(game_weight) * sign * game_factors[game]
                         + np.sqrt(team_weight) * team_factors[(game, team)])
        # Reorder the complete minutes/points pair. Marginal distributions and
        # within-player minutes/points relationships stay exactly unchanged.
        order = np.argsort(latent[:, i], kind='stable')
        source = np.argsort(outcomes.fd_points[:, i], kind='stable')
        points[order, i] = outcomes.fd_points[source, i]
        minutes[order, i] = outcomes.minutes[source, i]
    return OutcomeDraws(outcomes.fanduel_ids, minutes, points)


def candidate_sensitivity(outcomes, pool, rosters, *, seed=42):
    """Compare ceilings and candidate-set maximum, not contest win probability."""
    lineups, portfolios = [], []
    for scenario in SCENARIOS:
        sampled = correlated_draws(outcomes, pool, scenario, seed=seed)
        totals = sampled._lineup_totals(rosters)
        if not totals:
            raise ValueError('Supply legal candidate rosters.')
        labels = list(totals)
        matrix = np.column_stack(list(totals.values()))
        best = matrix.max(axis=1)
        ties = np.isclose(matrix, best[:, None], atol=1e-9, rtol=0)
        share = ties / ties.sum(axis=1, keepdims=True)
        for i, label in enumerate(labels):
            p50, p90, p95, p99 = np.quantile(matrix[:, i], [.5, .9, .95, .99])
            lineups.append({'Scenario': scenario, 'Lineup': label, 'Median': p50,
                            'P90': p90, 'P95': p95, 'P99': p99,
                            'Best among supplied candidates share': share[:, i].mean()})
        portfolios.append({'Scenario': scenario, 'Candidates': len(labels),
                           'Best candidate median': np.quantile(best, .5),
                           'Best candidate P90': np.quantile(best, .9),
                           'Best candidate P95': np.quantile(best, .95)})
    return pd.DataFrame(lineups), pd.DataFrame(portfolios)
