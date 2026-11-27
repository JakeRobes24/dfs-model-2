"""Historical NBA shot-mix forecasts using verified traditional box scores."""
import pandas as pd

from nba_possession_validation import _scheduled_player_rows
from opportunity_evidence import FD_WEIGHTS
from slate_import import team_code
from slate_research import played_minutes

SHOT_TYPES = ('twos', 'threes', 'free_throws')
VALUES = {'twos': 2, 'threes': 3, 'free_throws': 1}
FIELDS = ('fieldGoalsMade', 'fieldGoalsAttempted', 'threePointersMade',
          'threePointersAttempted', 'freeThrowsMade', 'freeThrowsAttempted')
MAKES = [f'{shot}_made' for shot in SHOT_TYPES]
ATTEMPTS = [f'{shot}_attempted' for shot in SHOT_TYPES]


def box_shooting_rows(game, payload):
    """Keep minutes, 2P/3P/FT identities and non-scoring FD components together."""
    day, game_id, away, home = game
    box = payload['boxScoreTraditional']
    if box['gameId'] != game_id:
        raise ValueError('Traditional box has the wrong scheduled game ID.')
    rows = []
    for side, club in [('awayTeam', away), ('homeTeam', home)]:
        source = box[side]
        if team_code(source['teamTricode']) != team_code(club):
            raise ValueError('Traditional box has the wrong scheduled team.')
        players = source['players']
        if len({row['personId'] for row in players}) != len(players):
            raise ValueError('Ambiguous player IDs in traditional box.')
        for player in players:
            stats = player['statistics']
            minutes = played_minutes(stats.get('minutes'))
            counts = {field: stats.get(field) for field in [*FIELDS, *FD_WEIGHTS]}
            if (minutes is None or not 10 <= minutes <= 60
                    or any(type(value) is not int or not 0 <= value <= 120 for value in counts.values())):
                continue
            fg, fga, threes, three_attempts, ft, fta = (counts[field] for field in FIELDS)
            makes = (fg-threes, threes, ft)
            attempts = (fga-three_attempts, three_attempts, fta)
            points = sum(value*count for value, count in zip(VALUES.values(), makes))
            if points != counts['points'] or any(not 0 <= made <= attempted
                                                for made, attempted in zip(makes, attempts)):
                continue
            other_fd = sum(counts[k]*weight for k, weight in FD_WEIGHTS.items() if k != 'points')
            rows.append(dict(date=day, game_id=game_id, team=team_code(club), nba_id=str(player['personId']),
                             minutes=minutes, points=points, non_points_fd=other_fd,
                             **dict(zip(MAKES, makes)), **dict(zip(ATTEMPTS, attempts))))
    return rows


def _window(rows):
    total = rows[[*MAKES, *ATTEMPTS, 'minutes', 'non_points_fd']].sum()
    makes = dict(zip(SHOT_TYPES, total[MAKES]))
    attempts = dict(zip(SHOT_TYPES, total[ATTEMPTS]))
    return makes, attempts, total['minutes'], total['non_points_fd']


def compare_shooting_workload(rows, schedule):
    """Hold four-game minutes and peripheral scoring fixed in the shot challengers."""
    rows = _scheduled_player_rows(rows, schedule)
    if rows.duplicated(['nba_id', 'game_id']).any():
        raise ValueError('Ambiguous NBA player-game shooting rows.')
    daily = rows.groupby('date')[[*MAKES, *ATTEMPTS]].sum()
    earlier = daily.cumsum().shift(1)
    output = []
    for _, history in rows.groupby(['nba_id', 'team']):
        history = history.sort_values('sequence').reset_index(drop=True)
        for index in range(8, len(history)):
            target = history.iloc[index]
            prior = history.iloc[index-8:index]
            if (list(prior.sequence) != list(range(target.sequence-8, target.sequence))
                    or not prior.date.lt(target.date).all()):
                continue
            cohort = earlier.loc[target.date]
            if not cohort[ATTEMPTS].ge(20).all():
                continue
            recent_makes, recent_attempts, recent_minutes, recent_fd = _window(prior.tail(4))
            long_makes, long_attempts, long_minutes, long_fd = _window(prior)
            rates = {k: cohort[m]/cohort[a] for k, m, a in zip(SHOT_TYPES, MAKES, ATTEMPTS)}
            recent_conversion = {k: recent_makes[k]/recent_attempts[k] if recent_attempts[k] else rates[k]
                                 for k in SHOT_TYPES}
            shrink = {k: (recent_makes[k]+20*rates[k])/(recent_attempts[k]+20) for k in SHOT_TYPES}
            long_conversion = {k: long_makes[k]/long_attempts[k] if long_attempts[k] else rates[k]
                               for k in SHOT_TYPES}
            recent_volume = {k: recent_attempts[k]/4 for k in SHOT_TYPES}
            long_volume = {k: long_attempts[k]/long_minutes*recent_minutes/4 for k in SHOT_TYPES}
            policies = {
                'Four-game baseline': (recent_volume, recent_conversion),
                'Four-game with pooled conversion': (recent_volume, shrink),
                'Eight-game volume only': (long_volume, recent_conversion),
                'Eight-game conversion only': (recent_volume, long_conversion),
                'Eight-game shot rates': (long_volume, long_conversion),
                'Eight-game volume and pooled conversion': (long_volume, shrink),
            }
            forecasts = {}
            for policy, (volume, conversion) in policies.items():
                scored = sum(VALUES[shot]*volume[shot]*conversion[shot] for shot in SHOT_TYPES)
                forecasts[policy] = (recent_minutes/4, scored, recent_fd/4)
            # Compare against the existing longer full-rate benchmark on the
            # exact same players before attributing any gain to shot mix.
            long_points = sum(VALUES[shot]*long_makes[shot] for shot in SHOT_TYPES)
            forecasts['Eight-game full rate, four-game minutes'] = (
                recent_minutes/4, long_points/long_minutes*recent_minutes/4, long_fd/long_minutes*recent_minutes/4)
            forecasts['Eight-game minutes and full rate'] = (long_minutes/8, long_points/8, long_fd/8)
            actual_fd = target.points+target.non_points_fd
            for policy, (minutes, scoring, other_fd) in forecasts.items():
                forecast = scoring+other_fd
                output.append(dict(date=target.date, game_id=target.game_id, team=target.team,
                                   nba_id=target.nba_id, policy=policy, shot_points=scoring,
                                   minutes=minutes, actual_points=target.points, forecast_fd=forecast,
                                   actual_fd=actual_fd, points_error=abs(scoring-target.points),
                                   minutes_error=abs(minutes-target.minutes),
                                   fd_error=abs(forecast-actual_fd),
                                   rate_error=abs(forecast/minutes-actual_fd/target.minutes)))
    return pd.DataFrame(output)
