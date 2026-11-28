"""Recover and compare historical NFL Classic candidates without a live projection feed."""
import argparse
from collections import Counter
from hashlib import file_digest
from itertools import combinations
import json
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from nba_group_dependence import normal_scores
from nfl_contest_import import NFL_SLOTS, import_nfl_contest
from nfl_daily_audit import ALIASES, game, norm, team
from nfl_dst_results import FIELDS, final_dst_scores
from nfl_role_dependence import fit_role_dependence, offensive_history, prior_game_forecasts

STACKS = {'WR': 'Same-team QB–WR', 'TE': 'Same-team QB–TE'}
EXTRA_WEIGHTS = {
    'fumbles_lost_total': -2, 'special_teams_tds': 6, 'fumble_recovery_tds': 6,
}


def recover_lineups(raw, archive):
    pool = import_nfl_contest(raw, expected_contest_id=archive['contest_id'])
    if archive['salary_cap'] != 60000:
        raise ValueError('Expected the Classic salary cap.')
    by_name = {}
    for player in pool:
        by_name.setdefault(player['player'], []).append(player)
    lineups = []
    for candidate in archive['lineups']:
        roster, clubs = [], Counter()
        for slot, name in zip(NFL_SLOTS, candidate['players'], strict=True):
            hits = by_name.get(name, ())
            if len(hits) != 1:
                raise ValueError(f'Missing or ambiguous contest identity for {name}.')
            player = hits[0]
            if (slot.rstrip('123') not in player['roster_eligibility']
                    or player['status'] == 'out'
                    or archive['all_player_salaries'][name] != player['salary']):
                raise ValueError(f'Archived slot, status or salary disagrees for {name}.')
            clubs[player['team']] += 1
            roster.append(dict(player, slot=slot))
        salary = sum(row['salary'] for row in roster)
        if (len({row['player_id'] for row in roster}) != len(NFL_SLOTS)
                or salary > archive['salary_cap'] or salary != candidate['salary_total']
                or len(clubs) < 3 or max(clubs.values()) > 4):
            raise ValueError('Archived lineup violates the original Classic roster constraints.')
        lineups.append(dict(candidate, salary=salary, roster=roster))
    return pool, lineups


def skill_results(workload, weekly, *, season):
    """Extend the verified offensive scoring with observed misc. scoring events."""
    history = offensive_history(workload, weekly, season=season)
    keys = ['game_id', 'gsis_id', 'team']
    stats = weekly.loc[weekly.season.eq(season) & weekly.season_type.eq('REG')].rename(
        columns={'player_id': 'gsis_id'})
    stats = stats[[*keys, *EXTRA_WEIGHTS, 'def_tds']].dropna(subset=keys)
    stats = stats.drop_duplicates(keys, keep=False)
    merged = history.merge(stats, on=keys, validate='one_to_one')
    fields = merged[list(EXTRA_WEIGHTS)]
    # An offensive player credited with a defensive TD needs settled scoring evidence.
    valid = np.isfinite(fields).all(axis=1) & fields.ge(0).all(axis=1) & merged.def_tds.eq(0)
    return merged.loc[valid, history.columns].assign(
        actual=merged.actual + fields.mul(EXTRA_WEIGHTS).sum(axis=1))


def _game_key(game_id):
    return game('@'.join(game_id.split('_')[2:]))


def _original_name(row):
    name = norm(row['player'])
    alias = ALIASES.get(row['player_id'].split('-')[1])
    return alias[1] if alias and (name, team(row['team'])) == (alias[0], alias[2]) else name


def _resolve_results(lineups, offense, defense, *, day):
    results = {}
    for row in (row for lineup in lineups for row in lineup['roster']):
        pid = row['player_id']
        if pid in results:
            continue
        position = row['positions'][0]
        history = defense if position == 'DEF' else offense.loc[offense.position.eq(position)]
        history = history.loc[history.team.map(team).eq(team(row['team']))]
        if position != 'DEF':
            names = history.loc[history.gameday.eq(day) & history.player.map(norm).eq(_original_name(row))]
            ids = names.loc[names.game_id.map(_game_key).eq(game(row['game'])), 'gsis_id'].unique()
            if len(ids) != 1:
                raise ValueError(f'Cannot establish a unique outcome identity for {row["player"]}.')
            history = history.loc[history.gsis_id.eq(ids[0])]
        resolved = history.loc[history.gameday.eq(day) & history.game_id.map(_game_key).eq(game(row['game']))]
        if len(resolved) != 1:
            raise ValueError(f'Cannot verify final score for {row["player"]}.')
        prior = history.loc[history.gameday.lt(day)].sort_values(['gameday', 'game_id']).tail(4)
        results[pid] = dict(player=row['player'], position=position, team=team(row['team']),
                            game=game(row['game']), actual=round(float(resolved.actual.iloc[0]), 2),
                            history_games=len(prior), baseline=float(prior.actual.mean()) if len(prior) else None)
    return results


def _defense_residuals(history, schedule):
    previous = []
    scores = history.set_index(['game_id', 'team']).actual
    for club in history.team.unique():
        games = schedule.loc[schedule.away_team.eq(club) | schedule.home_team.eq(club)]
        ids = games.sort_values(['gameday', 'game_id']).game_id
        values = scores.reindex(pd.MultiIndex.from_tuples([(gid, club) for gid in ids]))
        previous.extend((values-values.shift(1).rolling(4).mean()).dropna())
    return np.asarray(previous)


def compare_lineup_ranges(lineups, players, scales, rho):
    """Change QB/pass-catcher covariance while keeping the player marginals fixed."""
    ids = list(players)
    ordered = list(players.values())
    sd = np.asarray([scales[row['position']] for row in ordered])
    if not np.isfinite(sd).all() or (sd <= 0).any():
        raise ValueError('Missing or invalid earlier-season residual scale.')
    corr = np.eye(len(ids))
    for i, a in enumerate(ordered):
        for j, b in enumerate(ordered[:i]):
            if (a['team'], a['game']) != (b['team'], b['game']):
                continue
            if a['position'] == 'QB':
                catcher = b['position']
            elif b['position'] == 'QB':
                catcher = a['position']
            else:
                continue
            corr[i, j] = corr[j, i] = rho.get(catcher, 0.)
    minimum = float(np.linalg.eigvalsh(corr)[0])
    # A quarterback may have several modeled receivers. Shrink the joint matrix
    # if necessary while preserving the calibrated marginal variances.
    if minimum < .01:
        identity = np.eye(len(ids))
        corr = identity + (corr-identity)*(.99/(1-minimum))
    cov = corr*np.outer(sd, sd)
    policies = {'independent': np.diag(sd**2), 'qb_pass_catcher': cov}
    rows, forecasted = [], []
    for lineup in lineups:
        members = {row['player_id'] for row in lineup['roster']}
        selected = [row for pid, row in players.items() if pid in members]
        if len(selected) != len(NFL_SLOTS):
            raise ValueError('Lineup does not have all nine resolved members.')
        actual = round(sum(row['actual'] for row in selected), 2)
        result = dict(label=lineup['label'], salary=lineup['salary'], actual=actual,
                      archived_projection=lineup['projected_fd'])
        if all(row['history_games'] >= 2 for row in selected):
            center = sum(row['baseline'] for row in selected)
            mask = np.asarray([pid in members for pid in ids], dtype=float)
            result['historical_baseline'] = center
            result['ranges'] = {
                policy: normal_scores(actual, center, sqrt(mask @ matrix @ mask))
                for policy, matrix in policies.items()
            }
            forecasted.append((result, mask))
        rows.append(result)
    pairs = []
    for (left, left_mask), (right, right_mask) in combinations(forecasted, 2):
        # Shared players cancel in the lineup score difference.
        delta = left_mask-right_mask
        if not delta.any():
            continue
        margin = left['historical_baseline']-right['historical_baseline']
        won = .5 if left['actual'] == right['actual'] else float(left['actual'] > right['actual'])
        scores = {}
        for policy, matrix in policies.items():
            probability = .5*(1+erf(margin/sqrt(2*(delta @ matrix @ delta))))
            scores[policy] = dict(probability=probability, brier=(probability-won)**2)
        pairs.append(dict(left=left['label'], right=right['label'], shared_players=int(left_mask @ right_mask),
                          left_actual_win=won, policies=scores))
    return rows, pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = ('contest', 'archive', 'entered', 'schedule', 'training-stats', 'training-matched',
              'training-pbp', 'target-stats', 'target-matched', 'target-pbp')
    for name in (*inputs, 'output'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--training-season', type=int, required=True)
    args = parser.parse_args()
    archive = json.loads(args.archive.read_text())
    day = archive['slate_date']
    target_season = int(day[:4])
    if args.training_season >= target_season:
        raise ValueError('Use an earlier training season.')
    schedule = pd.read_csv(args.schedule)
    training_schedule = schedule.loc[schedule.season.eq(args.training_season)
                                     & schedule.game_type.eq('REG')]
    if training_schedule.empty or not training_schedule.gameday.lt(day).all():
        raise ValueError('Training schedule must precede the target slate.')
    pool, lineups = recover_lineups(args.contest.read_bytes(), archive)
    training_offense = skill_results(pd.read_csv(args.training_matched), pd.read_csv(args.training_stats, low_memory=False),
                                     season=args.training_season)
    target_offense = skill_results(pd.read_csv(args.target_matched), pd.read_csv(args.target_stats, low_memory=False),
                                   season=target_season)
    training_dst, training_rejected = final_dst_scores(pd.read_csv(args.training_pbp, usecols=FIELDS, low_memory=False),
                                                      schedule, season=args.training_season)
    target_dst, target_rejected = final_dst_scores(pd.read_csv(args.target_pbp, usecols=FIELDS, low_memory=False),
                                                  schedule, season=target_season)
    player_results = _resolve_results(lineups, target_offense, target_dst, day=day)
    entered = json.loads(args.entered.read_text())
    first = lineups[0]['roster']
    outcomes = [player_results[row['player_id']]['actual'] for row in first]
    if (entered['contest_id'] != archive['contest_id'] or entered['slate_date'] != day
            or len(entered['lineup']) != len(first)
            or any(a['player'] != b['player'] or a['actual_fd'] != actual
                   for a, b, actual in zip(entered['lineup'], first, outcomes))
            or round(sum(outcomes), 2) != entered['actual_total_fd']):
        raise ValueError('Reconstruction disagrees with the entered lineup settlement.')
    training = prior_game_forecasts(training_offense)
    scales = training.groupby('position').residual.std(ddof=0).to_dict()
    dst_residuals = _defense_residuals(training_dst, training_schedule)
    scales['DEF'] = float(np.std(dst_residuals))
    fitted = fit_role_dependence(training)
    rho = {position: fitted[label][1] for position, label in STACKS.items()}
    rows, pairs = compare_lineup_ranges(lineups, player_results, scales, rho)
    digests = {}
    for name in inputs:
        path = getattr(args, name.replace('-', '_'))
        with path.open('rb') as source:
            digests[name] = file_digest(source, 'sha256').hexdigest()
    output = dict(contest=archive['contest_id'], slate_date=day, pool_rows=len(pool),
                  games=len({p['game'] for p in pool}), pool_not_marked_out=sum(p['status'] != 'out' for p in pool),
                  input_sha256=digests,
                  training_season=args.training_season, residual_samples=training.position.value_counts().to_dict(),
                  dst_residual_samples=len(dst_residuals), residual_scales=scales, stack_correlations=rho,
                  training_dst_games=training_dst.game_id.nunique(), training_dst_rejected=training_rejected,
                  target_dst_games=target_dst.game_id.nunique(), target_dst_rejected=target_rejected,
                  players=list(player_results.values()), lineups=rows, lineup_pairs=pairs)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
