"""Describe observed rotations and teammate absence splits without changing projections."""
from collections import Counter, defaultdict
from statistics import mean

import pandas as pd

from slate_import import player_key


FD_WEIGHTS = {'points': 1, 'reboundsTotal': 1.2, 'assists': 1.5,
              'steals': 3, 'blocks': 3, 'turnovers': -1}


OPPORTUNITY_WEIGHTS = {'fieldGoalsAttempted': 1, 'freeThrowsAttempted': .44, 'turnovers': 1}


def complete_stat_rows(rows, weights):
    return [row for row in rows if all(type(row.get(stat)) in (int, float)
                                       and 0 <= row[stat] <= 150 for stat in weights)]


def rate_comparison(present, absent, weights):
    """Report observed and shrunk gaps with separate complete-stat denominators."""
    left, right = (complete_stat_rows(rows, weights) for rows in (present, absent))
    left_minutes, right_minutes = (sum(row['minutes'] for row in rows) for rows in (left, right))
    first, second = stat_rate(left, weights), stat_rate(right, weights)
    n = min(len(left), len(right))
    gap = second - first if first is not None and second is not None else None
    return dict(with_rate=first, without_rate=second, with_games=len(left), without_games=len(right),
                with_minutes=left_minutes, without_minutes=right_minutes,
                gap=gap, shrunk_gap=gap * n / (n + 5) if gap is not None else None,
                sufficient=n >= 3 and min(left_minutes, right_minutes) >= 60)


def stat_rate(rows, weights):
    """Minutes-weighted production using only rows with complete stat coverage."""
    available = complete_stat_rows(rows, weights)
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
        bench_logs = [row for row in logs if row.get('started') is False]
        start_logs = [row for row in logs if row.get('started') is True]
        role_fd = rate_comparison(bench_logs, start_logs, FD_WEIGHTS)
        role_opp = rate_comparison(bench_logs, start_logs, OPPORTUNITY_WEIGHTS)
        summaries.append({
            'fanduel_id': player.fanduel_id, 'Player': player.fanduel_name, 'Team': player.team,
            'Games observed': len(logs), 'Known starts': sum(starts_known) if starts_known else None,
            'Games with starter status': len(starts_known), 'Last played': logs[-1]['game_date'],
            'Minutes as starter': mean(row['minutes'] for row in start_logs) if start_logs else None,
            'Minutes off bench': mean(row['minutes'] for row in bench_logs) if bench_logs else None,
            'FD/min as starter': role_fd['without_rate'],
            'FD/min off bench': role_fd['with_rate'],
            'Starter complete FD games': role_fd['without_games'],
            'Bench complete FD games': role_fd['with_games'],
            'Starter complete FD minutes': role_fd['without_minutes'],
            'Bench complete FD minutes': role_fd['with_minutes'],
            'Starter/bench FD rate evidence': 'Observed comparison' if role_fd['sufficient'] else 'Small or incomplete sample',
            'Opportunities/min as starter': role_opp['without_rate'],
            'Opportunities/min off bench': role_opp['with_rate'],
            'Starter/bench opportunity evidence': 'Observed comparison' if role_opp['sufficient'] else 'Small or incomplete sample',
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
            with_player = [row for row in logs if teammate in row.get('teammates_played', ())
                           and teammate not in row.get('teammates_absent', ())]
            without_player = [row for row in logs if teammate in row.get('teammates_absent', ())
                              and teammate not in row.get('teammates_played', ())]
            if not without_player:
                continue
            absent_mean = mean(row['minutes'] for row in without_player)
            present_mean = mean(row['minutes'] for row in with_player) if with_player else None
            smaller = min(len(with_player), len(without_player))
            # Shrink small matched samples toward no change. This comparison is descriptive.
            shift = (absent_mean - present_mean) * smaller / (smaller + 5) if smaller else None
            fd = rate_comparison(with_player, without_player, FD_WEIGHTS)
            opportunity = rate_comparison(with_player, without_player, OPPORTUNITY_WEIGHTS)
            splits.append({
                'fanduel_id': player.fanduel_id, 'Player': player.fanduel_name, 'Out teammate': display,
                'Games with teammate': len(with_player), 'Games without teammate': len(without_player),
                'Minutes with': present_mean, 'Minutes without': absent_mean,
                'Minutes gap (shrunk)': shift,
                'FD/min with': fd['with_rate'],
                'FD/min without': fd['without_rate'],
                'FD/min gap': fd['gap'],
                'FD/min gap (shrunk)': fd['shrunk_gap'],
                'Complete FD games with': fd['with_games'],
                'Complete FD games without': fd['without_games'],
                'Complete FD minutes with': fd['with_minutes'],
                'Complete FD minutes without': fd['without_minutes'],
                'FD rate evidence': 'Observed comparison' if fd['sufficient'] else 'Small or incomplete sample',
                'Opportunities/min with': opportunity['with_rate'],
                'Opportunities/min without': opportunity['without_rate'],
                'Opportunities/min gap (shrunk)': opportunity['shrunk_gap'],
                'Complete opportunity games with': opportunity['with_games'],
                'Complete opportunity games without': opportunity['without_games'],
                'Complete opportunity minutes with': opportunity['with_minutes'],
                'Complete opportunity minutes without': opportunity['without_minutes'],
                'Opportunity rate evidence': 'Observed comparison' if opportunity['sufficient'] else 'Small or incomplete sample',
                'Evidence': 'Small sample' if smaller < 3 else 'Observed comparison',
                'Box-score sources': ' · '.join(sorted({row['source'] for row in with_player + without_player})),
            })
    return pd.DataFrame(summaries), pd.DataFrame(splits)
