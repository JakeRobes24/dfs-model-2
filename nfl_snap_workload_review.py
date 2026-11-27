"""Evaluate snap-based NFL workload and efficiency on matched final games."""

import numpy as np
import pandas as pd

from nfl_history_baseline_review import WEIGHTS
from nfl_yardage_validation import empirical_crps


def _unique(frame, columns):
    return frame.dropna(subset=columns).drop_duplicates(columns, keep=False)


def _yardage_draws(yards, volume, snaps, efficiency):
    """Compare yardage ranges from the same four completed player-games."""
    workload = np.multiply.outer(snaps, volume / snaps).ravel()
    # Ten opportunities anchor game-level efficiency, including zero-volume
    # games. A zero workload draw still produces zero yards.
    game_efficiency = (yards + 10 * efficiency) / (volume + 10)
    game_efficiency += efficiency - game_efficiency.mean()
    return {
        'Past yardage ranges': yards,
        'Snap/workload × fixed efficiency': workload * efficiency,
        'Snap/workload × variable efficiency': np.multiply.outer(workload, game_efficiency).ravel(),
    }


def reconcile_final_workload(schedule, snaps, stats, players, *, season, cutoff_day):
    """Join GSIS and PFR IDs, preserving only exact final game/team/opponent rows."""
    games = schedule.loc[
        schedule.season.eq(season) & schedule.game_type.eq('REG')
        & schedule.gameday.lt(cutoff_day) & schedule[['home_score', 'away_score']].notna().all(axis=1),
        ['game_id', 'week', 'gameday', 'home_team', 'away_team']]
    games = _unique(games, ['game_id'])
    home = games.rename(columns={'home_team': 'team', 'away_team': 'opponent'})
    away = games.rename(columns={'home_team': 'opponent', 'away_team': 'team'})
    clubs = pd.concat([home, away], ignore_index=True)
    clubs['team_game_number'] = clubs.sort_values(['gameday', 'game_id']).groupby('team').cumcount()
    keys = ['game_id', 'week', 'team', 'opponent']
    crosswalk = players[['pfr_id', 'gsis_id']].dropna().drop_duplicates()
    crosswalk = _unique(_unique(crosswalk, ['pfr_id']), ['gsis_id'])
    snap_rows = snaps.loc[snaps.season.eq(season) & snaps.game_type.eq('REG')].rename(
        columns={'pfr_player_id': 'pfr_id'})
    snap_rows = _unique(snap_rows, ['pfr_id', *keys]).merge(
        crosswalk, on='pfr_id', validate='many_to_one')
    metrics = ['carries', 'targets', 'rushing_yards', 'receiving_yards']
    stat_rows = stats.loc[stats.season.eq(season) & stats.season_type.eq('REG')].rename(
        columns={'player_id': 'gsis_id', 'opponent_team': 'opponent'})
    stat_rows = _unique(stat_rows, ['gsis_id', *keys]).loc[:, ['gsis_id', *keys, *metrics]]
    joined = snap_rows.merge(stat_rows, on=['gsis_id', *keys], validate='one_to_one').merge(
        clubs, on=keys, validate='many_to_one')
    joined = joined.loc[joined.position.isin(['QB', 'RB', 'WR', 'TE'])]
    valid = joined.offense_snaps.between(1, 115) & joined[['carries', 'targets']].ge(0).all(axis=1)
    valid &= joined[['carries', 'targets']].sum(axis=1).le(joined.offense_snaps)
    valid &= joined[['rushing_yards', 'receiving_yards']].abs().le(350).all(axis=1)
    return joined.loc[valid, ['gsis_id', 'pfr_id', 'player', 'team', 'opponent', 'position',
                              'game_id', 'gameday', 'week', 'team_game_number', 'offense_snaps', *metrics]]


def review_snap_workload(rows, *, minimum_volume=4):
    """Use four immediate team games and earlier role peers on each holdout.

    Frequency is conditional on a verified played game. Missing matches break
    the lookback. Forecasts are identical in coverage across each alternative.
    """
    prior_rates = {}
    for (day, pos), batch in rows.sort_values('gameday').groupby(['gameday', 'position']):
        prior_rates[pos, day] = batch[['carries', 'targets', 'rushing_yards', 'receiving_yards']].sum()
    rate_frame = pd.DataFrame.from_dict(prior_rates, orient='index').sort_index()
    if rate_frame.empty:
        return pd.DataFrame(), pd.DataFrame()
    earlier = rate_frame.groupby(level=0).cumsum() - rate_frame
    comparisons = []
    for (_, _), player in rows.groupby(['gsis_id', 'team']):
        player = player.sort_values('team_game_number')
        games = player.to_dict('records')
        for i in range(4, len(games)):
            four, current = games[i-4:i], games[i]
            last_game = current['team_game_number']
            if [row['team_game_number'] for row in four] != list(range(last_game-4, last_game)):
                continue
            if len({row['position'] for row in [*four, current]}) != 1:
                continue
            day, pos = current['gameday'], current['position']
            priors = earlier.loc[(pos, day)]
            snaps = np.array([row['offense_snaps'] for row in four])
            expected_snaps = np.average(snaps, weights=WEIGHTS['recent'])
            for measure, yardage in [('carries','rushing_yards'), ('targets','receiving_yards')]:
                volume, yards = (np.array([row[field] for row in four]) for field in (measure, yardage))
                if volume.sum() < minimum_volume or priors[measure] <= 0:
                    continue
                volume_by_snap = expected_snaps * volume.sum() / snaps.sum()
                shrunk_efficiency = ((yards.sum() + 10 * priors[yardage] / priors[measure])
                                     / (volume.sum() + 10))
                rows_for_measure = {
                    measure: {'Last game': volume[-1], 'Four game mean': volume.mean(),
                              'Recent weighted': np.average(volume, weights=WEIGHTS['recent']),
                              'Snaps × workload rate': volume_by_snap},
                    yardage: {'Last game': yards[-1], 'Four game mean': yards.mean(),
                              'Recent weighted': np.average(yards, weights=WEIGHTS['recent']),
                              'Snap workload × pooled yards': volume_by_snap * yards.sum()/volume.sum(),
                              'Snap workload × shrunk yards': volume_by_snap * shrunk_efficiency},
                }
                for metric, estimates in rows_for_measure.items():
                    for policy, estimate in estimates.items():
                        comparisons.append((day, current['week'], pos, metric, policy, current['gsis_id'],
                                            float(estimate), current[metric], abs(estimate-current[metric])))
                # Identical earlier games and expected volume. Estimate how
                # separating snaps and per-snap rate affects volume ranges.
                rates = volume / snaps
                for policy, draws in (
                    ('Past workload ranges', volume),
                    ('Independent snaps and rates', np.multiply.outer(snaps, rates).ravel()),
                ):
                    comparisons.append((day, current['week'], pos, measure + ' CRPS', policy,
                                        current['gsis_id'], float(np.mean(draws)), current[measure],
                                        empirical_crps(draws, current[measure])))
                for policy, draws in _yardage_draws(yards, volume, snaps, shrunk_efficiency).items():
                    comparisons.append((day, current['week'], pos, yardage + ' CRPS', policy,
                                        current['gsis_id'],
                                        float(np.mean(draws)), current[yardage],
                                        empirical_crps(draws, current[yardage])))
    details = pd.DataFrame(comparisons, columns=[
        'date', 'week', 'position', 'metric', 'policy', 'gsis_id', 'forecast', 'actual', 'error'])
    if details.empty:
        return details, pd.DataFrame()
    weekly = details.groupby(['metric', 'policy', 'week'], as_index=False).agg(
        error=('error', 'mean'), player_games=('error', 'size'))
    return details, weekly.groupby(['metric', 'policy'], as_index=False).agg(
        equal_week_error=('error', 'mean'), weeks=('week', 'size'), player_games=('player_games', 'sum'))
