"""Conservative FanDuel D/ST reconstruction from final nflverse play-by-play."""
import pandas as pd

FIELDS = (
    'game_id', 'game_date', 'season_type', 'week', 'play_id', 'play_type', 'away_team',
    'home_team', 'posteam', 'defteam',
    'touchdown', 'td_team', 'pass_touchdown', 'rush_touchdown', 'return_touchdown',
    'field_goal_result', 'extra_point_result', 'two_point_conv_result',
    'defensive_two_point_attempt', 'defensive_two_point_conv', 'punt_blocked', 'safety',
    'interception', 'sack', 'fumble_lost', 'fumbled_1_team', 'fumbled_2_team', 'fumble_recovery_1_team',
)


def _allowance(points):
    return next(value for bound, value in ((0, 10), (6, 7), (13, 4), (20, 1),
                                           (27, 0), (34, -1), (float('inf'), -4)) if points <= bound)


def _credits(play, clubs):
    """Return scoring events as (team, scoreboard points, offense points, DST points)."""
    attack, defense = play.posteam, play.defteam
    items = []
    if play.touchdown == 1:
        if play.td_team not in clubs:
            raise ValueError('Unknown touchdown team.')
        own_fumble = play.fumbled_1_team == attack and play.fumble_recovery_1_team == attack
        offensive = (play.td_team == attack and play.return_touchdown != 1
                     and (play.pass_touchdown == 1 or play.rush_touchdown == 1 or own_fumble))
        if not offensive and not (play.return_touchdown == 1 or play.td_team == defense):
            raise ValueError('Unclassified touchdown.')
        items.append((play.td_team, 6, 6 if offensive else 0, 0 if offensive else 6))
    if play.field_goal_result == 'made':
        items.append((attack, 3, 3, 0))
    if play.extra_point_result == 'good':
        items.append((attack, 1, 1, 0))
    if play.two_point_conv_result == 'success':
        items.append((attack, 2, 2, 0))
    if play.defensive_two_point_conv == 1:
        if play.defensive_two_point_attempt != 1:
            raise ValueError('Unclassified conversion return.')
        items.append((defense, 2, 0, 2))
    if play.safety == 1:
        items.append((defense, 2, 0, 2))
    if play.field_goal_result == 'blocked' or play.extra_point_result == 'blocked':
        raise ValueError('Blocked kick requires settled scoring evidence.')
    if play.punt_blocked == 1:
        items.append((defense, 0, 0, 2))
    conversion = (play.play_type == 'extra_point' or play.two_point_conv_result in ('success', 'failure')
                  or play.defensive_two_point_attempt == 1)
    if play.sack == 1 and not conversion:
        items.append((defense, 0, 0, 1))
    if play.interception == 1 and not conversion:
        items.append((defense, 0, 0, 2))
    if play.fumble_lost == 1 and not conversion:
        recovery = play.fumble_recovery_1_team
        if (play.fumbled_1_team not in clubs or recovery not in clubs
                or recovery == play.fumbled_1_team or pd.notna(play.fumbled_2_team)):
            raise ValueError('Ambiguous lost-fumble recovery.')
        items.append((recovery, 0, 0, 2))
    if any(team not in clubs for team, *_ in items):
        raise ValueError('Unrecognized scoring team.')
    return items


def final_dst_scores(plays, schedule, *, season):
    """Require exact final game IDs, club orientation and a reconciled scoreboard."""
    games = schedule.loc[schedule.season.eq(season) & schedule.game_type.eq('REG')
                         & schedule[['away_score', 'home_score']].notna().all(axis=1)]
    games = games.drop_duplicates('game_id', keep=False).set_index('game_id')
    plays = plays.loc[plays.game_id.isin(games.index) & plays.season_type.eq('REG')]
    rows, rejected = [], {}
    for gid in sorted(set(games.index) - set(plays.game_id)):
        rejected[gid] = 'Missing final play-by-play.'
    for gid, block in plays.groupby('game_id'):
        game = games.loc[gid]
        away, home = game.away_team, game.home_team
        if (not block.away_team.eq(away).all() or not block.home_team.eq(home).all()
                or not block.game_date.eq(game.gameday).all() or not block.week.eq(game.week).all()
                or not block.play_id.is_unique):
            rejected[gid] = 'Schedule or play identity mismatch.'
            continue
        clubs = away, home
        scoreboard = dict.fromkeys(clubs, 0)
        offense = dict.fromkeys(clubs, 0)
        events = dict.fromkeys(clubs, 0)
        try:
            valid = block.loc[block.play_type.ne('no_play')]
            for play in valid.itertuples(index=False):
                for team, points, offensive, dst in _credits(play, clubs):
                    scoreboard[team] += points
                    offense[team] += offensive
                    events[team] += dst
            if scoreboard != {away: game.away_score, home: game.home_score}:
                raise ValueError('Scoring events do not match final score.')
        except ValueError as exc:
            rejected[gid] = str(exc)
            continue
        for team, opponent in (clubs, clubs[::-1]):
            pa = offense[opponent]
            rows.append(dict(game_id=gid, gameday=game.gameday, week=int(game.week), team=team,
                             opponent=opponent, points_allowed=pa, event_points=events[team],
                             actual=_allowance(pa)+events[team]))
    return pd.DataFrame(rows), rejected
