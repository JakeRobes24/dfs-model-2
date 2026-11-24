"""Descriptive pre-slate matchup context from completed NBA team boxes."""
from collections import defaultdict
from statistics import mean

import pandas as pd

from slate_import import matchup_key, team_code


def team_box_context(game):
    """Estimate possessions from both team totals; normalize overtime to 48 minutes."""
    period = game.get('period')
    if game.get('gameStatus') != 3 or type(period) is not int or not 4 <= period <= 8:
        return {}
    duration = 48 + 5 * (period - 4)
    teams = {}
    for side in ('awayTeam', 'homeTeam'):
        club = game.get(side) or {}
        team = team_code(club.get('teamTricode', ''))
        stats = club.get('statistics') or {}
        fga, fta, orb, to, points = (stats.get('fieldGoalsAttempted'), stats.get('freeThrowsAttempted'),
                                    stats.get('reboundsOffensive'),
                                    stats.get('turnoversTotal', stats.get('turnovers')), stats.get('points'))
        values = (fga, fta, orb, to, points)
        if (not team or team in teams or not all(type(v) in (int, float) and 0 <= v <= 250 for v in values)
                or fga <= 0 or orb > fga):
            return {}
        poss = fga + .44 * fta - orb + to
        if not 50 <= poss * 48 / duration <= 150:
            return {}
        teams[team] = (poss, points)
    pace = mean(v[0] for v in teams.values()) * 48 / duration
    possessions = pace * duration / 48
    return {team: dict(team_pace48=pace, team_off_rating=100 * points / possessions,
                       team_def_rating=100 * teams[other][1] / possessions)
            for team, (_, points) in teams.items() for other in teams if other != team}


def matchup_context(pool, rotations, slate, *, game_limit=3):
    """Use one unique complete team-game observation, strictly before the slate."""
    if not 1 <= game_limit <= 10:
        raise ValueError('Choose one to ten recent team games.')
    groups = defaultdict(set)
    for row in rotations:
        try:
            day, team = row['game_date'], row['team']
            game = matchup_key(row['game'])
            source = row['source']
            values = tuple(float(row[k]) for k in ('team_pace48', 'team_off_rating', 'team_def_rating'))
            if (day >= slate or not team or team not in game.split('/') or not source
                    or not 50 <= values[0] <= 150
                    or not all(0 <= value <= 250 for value in values[1:])):
                continue
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
        groups[(team, day, game)].add((*values, source))
    observations = defaultdict(list)
    for (team, day, game), records in groups.items():
        if len(records) == 1:
            observations[team].append((day, game, *next(iter(records))))
    summary = {}
    for team, rows in observations.items():
        # Multiple games for the same team/date are ambiguous, not two samples.
        day_counts = defaultdict(int)
        for row in rows:
            day_counts[row[0]] += 1
        chosen = sorted((row for row in rows if day_counts[row[0]] == 1), reverse=True)[:game_limit]
        if chosen:
            summary[team] = (len(chosen), mean(r[2] for r in chosen),
                             mean(r[3] for r in chosen), mean(r[4] for r in chosen),
                             ' · '.join(sorted({r[5] for r in chosen})))
    output = []
    for row in pool.itertuples():
        teams = matchup_key(row.game).split('/')
        if len(teams) != 2 or row.team not in teams:
            continue
        opponent = next(t for t in teams if t != row.team)
        own = summary.get(row.team, (0, None, None, None, ''))
        opp = summary.get(opponent, (0, None, None, None, ''))
        output.append(dict(fanduel_id=row.fanduel_id, opponent=opponent,
                           team_games=own[0], opponent_games=opp[0],
                           team_pace48=own[1], opponent_pace48=opp[1],
                           descriptive_pace_mean=mean([own[1], opp[1]]) if own[0] and opp[0] else None,
                           team_off_rating=own[2], opponent_def_rating=opp[3],
                           matchup_sample='Recent context' if min(own[0], opp[0]) >= 3 else 'Small or missing sample',
                           team_sources=own[4], opponent_sources=opp[4]))
    return pd.DataFrame(output)
