"""Audit PBP Stats possession and usage evidence on dated NBA team games."""
import math

import pandas as pd

from opportunity_evidence import FD_WEIGHTS
from slate_import import team_code
from slate_research import played_minutes

PBP_FIELDS = {'points': 'Points', 'reboundsTotal': 'Rebounds', 'assists': 'Assists',
              'steals': 'Steals', 'blocks': 'Blocks', 'turnovers': 'Turnovers'}


def possession_rows(schedule_game, payload):
    """Match a PBP Stats response to the official schedule used for its request."""
    day, game_id, away, home = schedule_game
    if (payload.get('league') != 'nba' or payload.get('date') != day
            or team_code(payload.get('away_team_abbreviation', '')) != team_code(away)
            or team_code(payload.get('home_team_abbreviation', '')) != team_code(home)):
        raise ValueError('Possessions response does not match the scheduled NBA game.')
    rows = []
    for side, club in (('Away', away), ('Home', home)):
        players = payload['stats'][side]['FullGame']
        ids = [str(player.get('EntityId', '')) for player in players]
        if len(ids) != len(set(ids)):
            raise ValueError('Ambiguous possession player IDs.')
        for pid, player in zip(ids, players):
            minutes = played_minutes(player.get('Minutes'))
            if not pid.isdigit() or pid == '0' or minutes is None or minutes < 10:
                continue
            possessions = player.get('OffPoss')
            components = [player.get(field, 0) for field in PBP_FIELDS.values()]
            if (type(possessions) not in (int, float) or not 1 <= possessions <= 160
                    or any(type(v) not in (int, float) or not 0 <= v <= 100 for v in components)):
                continue
            usage = player.get('Usage')
            if type(usage) not in (int, float) or not 0 <= usage <= 100:
                usage = None
            points = sum(FD_WEIGHTS[field] * value for field, value in zip(PBP_FIELDS, components))
            rows.append(dict(game_id=game_id, date=day, team=team_code(club), nba_id=pid,
                             minutes=minutes, possessions=possessions, usage=usage, fd=points))
    return rows


def official_possession_rows(schedule_game, advanced, traditional):
    """Join NBA advanced and traditional boxes by exact game, club and player."""
    day, game_id, away, home = schedule_game
    adv, box = advanced['boxScoreAdvanced'], traditional['boxScoreTraditional']
    if adv['gameId'] != game_id or box['gameId'] != game_id:
        raise ValueError('Official box does not match schedule game ID.')
    rows = []
    for side, club in (('awayTeam', away), ('homeTeam', home)):
        adv_team, box_team = adv[side], box[side]
        if (adv_team['teamId'] != box_team['teamId']
                or any(team_code(t['teamTricode']) != team_code(club) for t in (adv_team, box_team))):
            raise ValueError('Official box does not match scheduled team.')
        by_id = {p['personId']: p['statistics'] for p in box_team['players']}
        adv_ids = {p['personId'] for p in adv_team['players']}
        if len(by_id) != len(box_team['players']) or len(adv_ids) != len(adv_team['players']):
            raise ValueError('Ambiguous official player IDs.')
        for player in adv_team['players']:
            stats = player['statistics']
            pid = player['personId']
            counting = by_id.get(pid, {})
            minutes = played_minutes(stats.get('minutes'))
            possessions, usage = stats.get('possessions'), stats.get('usagePercentage')
            components = [counting.get(field) for field in FD_WEIGHTS]
            if (minutes is None or minutes < 10 or minutes != played_minutes(counting.get('minutes'))
                    or type(possessions) not in (int, float) or not 1 <= possessions <= 160
                    or any(type(v) not in (int, float) or not 0 <= v <= 100 for v in components)):
                continue
            if type(usage) not in (int, float) or not 0 <= usage <= 1:
                usage = None
            points = sum(weight * value for weight, value in zip(FD_WEIGHTS.values(), components))
            rows.append(dict(game_id=game_id, date=day, team=team_code(club), nba_id=str(pid),
                             minutes=minutes, possessions=possessions,
                             usage=None if usage is None else usage * 100, fd=points))
    return rows


def _scheduled_player_rows(rows, schedule):
    games = pd.DataFrame(schedule, columns=['date', 'game_id', 'away', 'home'])
    if not games.game_id.is_unique:
        raise ValueError('Require unique scheduled games.')
    sides = pd.concat([games[['date', 'game_id', side]].rename(columns={side: 'team'})
                       for side in ('away', 'home')], ignore_index=True)
    sides['team'] = sides.team.map(team_code)
    sides['sequence'] = sides.sort_values(['date', 'game_id']).groupby('team').cumcount()
    return rows.merge(sides, on=['game_id', 'team', 'date'], validate='many_to_one')


def compare_possession_forecasts(rows, schedule):
    """Use identical played holdouts and four consecutive earlier team games."""
    rows = _scheduled_player_rows(rows, schedule)
    if rows.duplicated(['game_id', 'nba_id'], keep=False).any():
        raise ValueError('Ambiguous duplicate NBA player-game observations.')
    detail = []
    for _, group in rows.groupby(['nba_id', 'team']):
        ordered = group.sort_values('sequence').to_dict('records')
        for i in range(4, len(ordered)):
            prior, target = ordered[i-4:i], ordered[i]
            last = target['sequence']
            if [row['sequence'] for row in prior] != list(range(last-4, last)):
                continue
            minutes = sum(row['minutes'] for row in prior) / 4
            rate_per_minute = sum(row['fd'] for row in prior) / (4*minutes)
            long_pace = sum(row['possessions'] for row in prior) / (4*minutes)
            recent_pace = sum(row['possessions'] for row in prior[-2:]) / sum(
                row['minutes'] for row in prior[-2:])
            baseline = minutes * rate_per_minute
            forecast = baseline * (long_pace + recent_pace) / (2*long_pace)
            usage_baseline = usage_recent = math.nan
            if all(pd.notna(row['usage']) for row in [*prior, target]):
                usage_baseline = abs(sum(row['usage'] for row in prior)/4 - target['usage'])
                usage_recent = abs(sum(row['usage'] for row in prior[-2:])/2 - target['usage'])
            detail.append(dict(date=target['date'], nba_id=target['nba_id'],
                               game_id=target['game_id'], team=target['team'],
                               baseline_fd_error=abs(baseline-target['fd']),
                               possession_fd_error=abs(forecast-target['fd']),
                               baseline_usage_error=usage_baseline, recent_usage_error=usage_recent))
    return pd.DataFrame(detail, columns=['date', 'nba_id', 'game_id', 'team', 'baseline_fd_error',
                                         'possession_fd_error', 'baseline_usage_error', 'recent_usage_error'])
