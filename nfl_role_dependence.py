"""Historical NFL same-game offensive scoring dependence by position pairing."""
from collections import defaultdict
from math import sqrt

import numpy as np
import pandas as pd

from nba_group_dependence import normal_scores

SCORE_WEIGHTS = {
    'passing_yards': .04, 'passing_tds': 4, 'passing_interceptions': -1,
    'rushing_yards': .1, 'rushing_tds': 6, 'receiving_yards': .1,
    'receiving_tds': 6, 'receptions': .5, 'passing_2pt_conversions': 2,
    'rushing_2pt_conversions': 2, 'receiving_2pt_conversions': 2,
}
BONUSES = {'passing_yards': 300, 'rushing_yards': 100, 'receiving_yards': 100}
CHECKS = ['carries', 'targets', 'rushing_yards', 'receiving_yards']
KEYS = ['gsis_id', 'team', 'opponent', 'game_id', 'week', 'position']
PAIR_TYPES = (
    ('Same-team QB–WR', 'QB', 'WR', True),
    ('Same-team QB–TE', 'QB', 'TE', True),
    ('Same-team QB–RB', 'QB', 'RB', True),
    ('Same-team WR–WR', 'WR', 'WR', True),
    ('Same-team RB–WR', 'RB', 'WR', True),
    ('Same-team RB–RB', 'RB', 'RB', True),
    ('Opposing QB–WR', 'QB', 'WR', False),
    ('Opposing QB–QB', 'QB', 'QB', False),
)


def offensive_history(workload, weekly, *, season):
    """Match exact regular-season identity, position and counting statistics."""
    fields = list(dict.fromkeys([*CHECKS, *SCORE_WEIGHTS]))
    stats = weekly.loc[weekly.season.eq(season) & weekly.season_type.eq('REG')].rename(
        columns={'player_id': 'gsis_id', 'opponent_team': 'opponent'})
    stats = stats[[*KEYS, *fields]].dropna(subset=KEYS).drop_duplicates(KEYS[:-1], keep=False)
    matched = workload.merge(stats, on=KEYS, suffixes=('', '_source'), validate='one_to_one')
    values = matched[[f'{k}_source' if k in CHECKS else k for k in SCORE_WEIGHTS]].copy()
    values.columns = list(SCORE_WEIGHTS)
    same = pd.Series(True, index=matched.index)
    for key in CHECKS:
        same &= matched[key].eq(matched[f'{key}_source'])
    valid = same & np.isfinite(values).all(axis=1)
    valid &= values[[col for col in values if 'yards' not in col]].ge(0).all(axis=1)
    score = values.mul(SCORE_WEIGHTS).sum(axis=1, min_count=len(SCORE_WEIGHTS))
    for col, threshold in BONUSES.items():
        score += 3*values[col].ge(threshold)
    return matched.loc[valid, workload.columns].assign(actual=score.loc[valid])


def prior_game_forecasts(history):
    """Compute the four-earlier-game baseline for players with verified appearances."""
    output = []
    for _, players in history.groupby(['gsis_id', 'team']):
        games = players.sort_values('team_game_number').to_dict('records')
        for i in range(4, len(games)):
            prior, target = games[i-4:i], games[i]
            seq = target['team_game_number']
            if ([row['team_game_number'] for row in prior] != list(range(seq-4, seq))
                    or any(row['position'] != target['position'] or row['gameday'] >= target['gameday']
                           for row in prior)):
                continue
            forecast = sum(row['actual'] for row in prior)/4
            output.append(dict(target, forecast=forecast, residual=target['actual']-forecast))
    return pd.DataFrame(output)


def _pairs(forecasts):
    """Choose role leaders by forecast among the played historical cohort."""
    pairs = defaultdict(list)
    for game_id, game in forecasts.groupby('game_id'):
        clubs = sorted(game.team.unique())
        if len(clubs) != 2:
            continue
        slots = {
            key: group.sort_values(['forecast', 'gsis_id'], ascending=[False, True]).to_dict('records')
            for key, group in game.groupby(['team', 'position'])
        }
        for label, first, second, teammate in PAIR_TYPES:
            for club, opponent in (clubs, clubs[::-1]):
                if not teammate and first == second and club != clubs[0]:
                    continue
                a = slots.get((club, first), ())
                b = slots.get((club if teammate else opponent, second), ())
                offset = int(teammate and first == second)
                if a and len(b) > offset:
                    pairs[label].append((game_id, a[0], b[offset]))
    return pairs


def fit_role_dependence(training, *, minimum_games=40):
    """Fit residual scales and shrunk correlations for the tracked position pairs."""
    if minimum_games < 1:
        raise ValueError('At least one earlier training game is required.')
    trained = {}
    for label, pairs in _pairs(training).items():
        games = len({game for game, _, _ in pairs})
        if games < minimum_games:
            continue
        left, right = ([pair[part]['residual'] for pair in pairs] for part in (1, 2))
        scale = np.asarray([np.std(left), np.std(right)])
        if not np.isfinite(scale).all() or (scale <= 0).any():
            continue
        rho = float(np.clip(np.corrcoef(left, right)[0, 1]*games/(games+75), -.5, .5))
        trained[label] = scale, rho, games
    return trained


def compare_frozen_role_dependence(training, evaluation, *, minimum_games=40):
    """Train only earlier-season residual scales and correlations on matched pairs."""
    if training.empty or evaluation.empty:
        return pd.DataFrame()
    if (training.gameday.isna().any() or evaluation.gameday.isna().any()
            or training.gameday.max() >= evaluation.gameday.min()):
        raise ValueError('Dependence training must end before evaluation.')
    eval_pairs = _pairs(evaluation)
    rows = []
    for label, (scale, rho, games) in fit_role_dependence(training, minimum_games=minimum_games).items():
        for game_id, a, b in eval_pairs.get(label, ()):
            center = a['forecast'] + b['forecast']
            actual = a['actual'] + b['actual']
            for policy, dependence in [('Independent', 0.), ('Frozen role dependence', rho)]:
                sd = sqrt(float(scale@scale + 2*dependence*scale.prod()))
                rows.append(dict(pair=label, game_id=game_id, week=a['week'], policy=policy,
                                 correlation=dependence, training_games=games,
                                 **normal_scores(actual, center, sd)))
    return pd.DataFrame(rows)
