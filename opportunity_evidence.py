"""Describe observed rotations and teammate absence splits without changing projections."""
from collections import Counter, defaultdict
from statistics import mean
from math import isfinite

import pandas as pd

from slate_import import player_key


FD_WEIGHTS = {'points': 1, 'reboundsTotal': 1.2, 'assists': 1.5,
              'steals': 3, 'blocks': 3, 'turnovers': -1}


OPPORTUNITY_WEIGHTS = {'fieldGoalsAttempted': 1, 'freeThrowsAttempted': .44, 'turnovers': 1}


def complete_stat_rows(rows, weights):
    return [row for row in rows if type(row.get('minutes')) in (int, float)
            and isfinite(row['minutes']) and 0 < row['minutes'] <= 60
            and all(type(row.get(stat)) in (int, float)
                    and 0 <= row[stat] <= 150 for stat in weights)]


def component_rate_evidence(rows):
    """Joint complete-stat sample: net scoring, peripheral FD, opportunity proxy.
    
    Opportunities are FGA + .44 FTA + turnovers, NOT official usage percentage.
    Never divide rates derived from different sets of games.
    """
    complete = complete_stat_rows(rows, FD_WEIGHTS | OPPORTUNITY_WEIGHTS)
    minutes = sum(r['minutes'] for r in complete)
    opportunities = sum(sum(r[k]*w for k,w in OPPORTUNITY_WEIGHTS.items()) for r in complete)
    net = sum(r['points']-r['turnovers'] for r in complete)
    peripheral = sum(sum(r[k]*w for k,w in FD_WEIGHTS.items()
                         if k not in ('points','turnovers')) for r in complete)
    return dict(games=len(complete), minutes=minutes,
                opportunities_per_minute=opportunities/minutes if minutes else None,
                net_per_opportunity=net/opportunities if opportunities else None,
                peripheral_per_minute=peripheral/minutes if minutes else None)


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


def role_matched_absence(present, absent):
    """Descriptive within-role comparisons, never an additive teammate boost.

    Unknown roles cannot establish a same-role comparison. Use overlap
    weights (smaller sample in each stratum) rather than comparing unlike
    role mixtures. Report sample sufficiency separately for minutes and rate.
    """
    groups = []
    for role in (True, False):
        left = [row for row in present if row.get('started') is role]
        right = [row for row in absent if row.get('started') is role]
        if not left or not right:
            continue
        n = min(len(left), len(right))
        minute_gap = mean(r['minutes'] for r in right) - mean(r['minutes'] for r in left)
        fd = rate_comparison(left, right, FD_WEIGHTS)
        opp = rate_comparison(left, right, OPPORTUNITY_WEIGHTS)
        groups.append((n, minute_gap, fd, opp))
    n = sum(g[0] for g in groups)
    def weighted_rate(index):
        usable = [(min(g[index]['with_games'], g[index]['without_games']), g[index]['gap'])
                  for g in groups if g[index]['gap'] is not None]
        count = sum(k for k, _ in usable)
        gap = sum(k * v for k, v in usable) / count if count else None
        return count, gap
    fd_n, fd_gap = weighted_rate(2)
    opp_n, opp_gap = weighted_rate(3)
    gap = sum(g[0] * g[1] for g in groups) / n if n else None
    return {
        'Role-matched strata': len(groups),
        'Role-matched games per side': n,
        'Role-matched minutes gap': gap,
        'Role-matched minutes gap (shrunk)': gap * n / (n + 5) if n else None,
        'Role-matched FD games per side': fd_n,
        'Role-matched FD/min gap': fd_gap,
        'Role-matched opportunity games per side': opp_n,
        'Role-matched opportunities/min gap': opp_gap,
        'Role-matched evidence': ('Observed comparison' if n >= 3 else
                                  'Small sample' if n else 'No overlapping known roles'),
    }


def teammate_participation(row, teammate):
    """Require explicit and mutually exclusive historical participation."""
    played = teammate in row.get('teammates_played', ())
    absent = teammate in row.get('teammates_absent', ())
    return 'played' if played and not absent else 'absent' if absent and not played else 'unknown'


def box_sources(rows):
    # Preserve both official production and explicit secondary role evidence.
    return ' · '.join(sorted({source for r in rows
                             for source in (r.get('source'),r.get('historical_role_source'))
                             if isinstance(source,str) and source.strip()}))


def opportunity_evidence(pool, rotations, slate):
    logs_by_player = defaultdict(list)
    for row in rotations:
        if row['game_date'] < slate and row.get('nba_id') and 0 < row['minutes'] <= 60:
            logs_by_player[(row['team'], player_key(row['player']))].append(row)

    pool_keys = [(player.team, player_key(player.fanduel_name)) for player in pool.itertuples()]
    pool_counts = Counter(pool_keys)
    unavailable = defaultdict(list)
    for player, key in zip(pool.itertuples(), pool_keys):
        if player.prelock_status in ('out', 'inactive', 'suspended') and pool_counts[key] == 1:
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
        component_samples = {}
        for prefix, group in [('recent', logs), ('starter', start_logs), ('bench', bench_logs)]:
            component_samples.update({f'component_{prefix}_{key}': value
                                      for key,value in component_rate_evidence(group).items()})
        summaries.append({
            **component_samples,
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
            'Box-score sources': box_sources(logs),
        })
        for teammate, display in unavailable[player.team]:
            with_player = [row for row in logs if teammate_participation(row, teammate) == 'played']
            without_player = [row for row in logs if teammate_participation(row, teammate) == 'absent']
            # Multiple simultaneously absent teammates can confound a single
            # absence split. Isolate games where every other current scratch
            # was explicitly observed playing, and report separately.
            other = [key for key, _ in unavailable[player.team] if key != teammate]
            clean_with = [row for row in with_player
                          if all(teammate_participation(row, key) == 'played' for key in other)]
            clean_without = [row for row in without_player
                             if all(teammate_participation(row, key) == 'played' for key in other)]
            isolated = role_matched_absence(clean_with, clean_without)
            # A prospective single-absence hypothesis needs the player's
            # currently confirmed role and no other known current scratch.
            role = getattr(player, 'prelock_starter', '')
            left = [r for r in clean_with if role in ('starter','bench')
                    and r.get('started') is (role == 'starter')]
            right = [r for r in clean_without if role in ('starter','bench')
                     and r.get('started') is (role == 'starter')]
            current_role = role_matched_absence(left, right)
            current_fd = rate_comparison(left, right, FD_WEIGHTS)
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
                **role_matched_absence(with_player, without_player),
                'Other currently out teammates': len(other),
                'Isolated games with teammate': len(clean_with),
                'Isolated games without teammate': len(clean_without),
                'Isolated role-matched games per side': isolated['Role-matched games per side'],
                'Isolated role-matched minutes gap (shrunk)': isolated['Role-matched minutes gap (shrunk)'],
                'Isolated role-matched FD/min gap': isolated['Role-matched FD/min gap'],
                'Current confirmed role': role if role in ('starter','bench') else '',
                'Current role games per side': current_role['Role-matched games per side'],
                'Current role minutes gap (shrunk)': current_role['Role-matched minutes gap (shrunk)'],
                'Current role FD/min without': current_fd['without_rate'] if current_fd['sufficient'] else None,
                'Current role complete FD games per side': min(current_fd['with_games'], current_fd['without_games']),
                'Current role complete FD minutes per side': min(current_fd['with_minutes'], current_fd['without_minutes']),
                'Box-score sources': box_sources(with_player + without_player),
            })
    return pd.DataFrame(summaries), pd.DataFrame(splits)
