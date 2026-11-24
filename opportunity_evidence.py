"""Describe observed rotations and teammate absence splits without changing projections."""
from collections import Counter, defaultdict
from statistics import mean

import pandas as pd

from slate_import import player_key


FD_WEIGHTS = {'points': 1, 'reboundsTotal': 1.2, 'assists': 1.5,
              'steals': 3, 'blocks': 3, 'turnovers': -1}


def stat_rate(rows, weights):
    """Minutes-weighted production using only rows with complete stat coverage."""
    available = [row for row in rows if all(type(row.get(stat)) in (int, float)
                                            and 0 <= row[stat] <= 150 for stat in weights)]
    if not available:
        return None
    return sum(sum(row[stat] * weight for stat, weight in weights.items()) for row in available) / sum(
        row['minutes'] for row in available)


def opportunity_evidence(pool, rotations, slate):
    logs_by_player = defaultdict(list)
    for row in rotations:
        if row['game_date'] < slate and row.get('nba_id') and 0 < row['minutes'] <= 60:
            logs_by_player[(row['team'], player_key(row['player']))].append(row)

    pool_keys = [(player.team, player_key(player.fanduel_name)) for player in pool.itertuples()]
    pool_counts = Counter(pool_keys)
    unavailable = defaultdict(list)
    for player, key in zip(pool.itertuples(), pool_keys):
        if player.prelock_status == 'out' and pool_counts[key] == 1:
            unavailable[player.team].append((key[1], player.fanduel_name))

    summaries, splits = [], []
    for player, key in zip(pool.itertuples(), pool_keys):
        if not player.eligible or pool_counts[key] != 1:
            continue
        logs = logs_by_player.get(key, [])
        if not logs or len({row['nba_id'] for row in logs}) != 1:
            continue
        counts = Counter(row['game_date'] for row in logs)
        logs = sorted((row for row in logs if counts[row['game_date']] == 1), key=lambda row: row['game_date'])
        if not logs:
            continue
        minutes = [row['minutes'] for row in logs]
        starts_known = [row['started'] for row in logs if row.get('started') is not None]
        summaries.append({
            'fanduel_id': player.fanduel_id, 'Player': player.fanduel_name, 'Team': player.team,
            'Games observed': len(logs), 'Known starts': sum(starts_known) if starts_known else None,
            'Games with starter status': len(starts_known), 'Last played': logs[-1]['game_date'],
            'Last 5 minutes': mean(minutes[-5:]) if len(logs) >= 5 else None,
            'Last 10 minutes': mean(minutes[-10:]) if len(logs) >= 10 else None,
            'FD points per minute': stat_rate(logs, FD_WEIGHTS),
            'Games with complete FD stats': sum(all(type(row.get(stat)) in (int, float)
                                                    and 0 <= row[stat] <= 150
                                                    for stat in FD_WEIGHTS) for row in logs),
            'Minutes with complete FD stats': sum(row['minutes'] for row in logs
                                                  if all(type(row.get(stat)) in (int, float)
                                                         and 0 <= row[stat] <= 150
                                                         for stat in FD_WEIGHTS)),
            'Shot/FT/turnover opportunities per minute': stat_rate(
                logs, {'fieldGoalsAttempted': 1, 'freeThrowsAttempted': .44, 'turnovers': 1}),
            'Box-score sources': ' · '.join(sorted({row['source'] for row in logs})),
        })
        for teammate, display in unavailable[player.team]:
            with_player = [row for row in logs if teammate in row.get('teammates_played', ())]
            without_player = [row for row in logs if teammate in row.get('teammates_absent', ())]
            if not without_player:
                continue
            absent_mean = mean(row['minutes'] for row in without_player)
            present_mean = mean(row['minutes'] for row in with_player) if with_player else None
            smaller = min(len(with_player), len(without_player))
            # Shrink small matched samples toward no change. This comparison is descriptive.
            shift = (absent_mean - present_mean) * smaller / (smaller + 5) if smaller else None
            splits.append({
                'fanduel_id': player.fanduel_id, 'Player': player.fanduel_name, 'Out teammate': display,
                'Games with teammate': len(with_player), 'Games without teammate': len(without_player),
                'Minutes with': present_mean, 'Minutes without': absent_mean,
                'Minutes gap (shrunk)': shift,
                'FD/min with': stat_rate(with_player, FD_WEIGHTS),
                'FD/min without': stat_rate(without_player, FD_WEIGHTS),
                'Evidence': 'Small sample' if smaller < 3 else 'Observed comparison',
                'Box-score sources': ' · '.join(sorted({row['source'] for row in with_player + without_player})),
            })
    return pd.DataFrame(summaries), pd.DataFrame(splits)
