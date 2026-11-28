"""Dated NBA tracked chances and conversion tests on complete team-game windows."""
import re

import pandas as pd
from bs4 import BeautifulSoup

from nba_possession_validation import _scheduled_player_rows
from slate_import import player_key, team_code
from slate_research import played_minutes

TRACKING_COLUMNS = ['Game', 'Min', 'Ast', 'Pot. ast', 'Reb', 'Reb ch.', 'Touches',
                    'Drives', 'Passes', 'C&S 3PA', 'Defl.']


def nba_house_potential_assists(raw):
    """Read the public dated tracking log, retaining actuals for cross-checking."""
    soup = BeautifulSoup(raw, 'html.parser')
    headers = soup.find_all('h1')
    tables = [table for table in soup.find_all('table')
              if [cell.get_text(' ', strip=True) for cell in table.select('thead th')] == TRACKING_COLUMNS]
    if len(headers) != 1 or len(tables) != 1:
        raise ValueError('Expected one NBA House player tracking log.')
    name = player_key(headers[0].get_text(' ', strip=True))
    rows = []
    for tr in tables[0].select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != len(TRACKING_COLUMNS):
            continue
        link = cells[0].find('a', href=True)
        match = re.fullmatch(r'/game/(\d{4}-\d{2}-\d{2})/([a-z]+)-at-([a-z]+)', link['href']) if link else None
        # Rebound chances are not used to validate potential assists. Require
        # the counting-box rebounds for the independent identity cross-check,
        # but do not discard a valid assist observation solely for a missing
        # unrelated tracking channel.
        values = [cell.get_text(' ', strip=True) for cell in cells[1:5]]
        if not match or not all(value.isdecimal() for value in values):
            continue
        minutes, assists, potential, rebounds = map(int, values)
        if 0 <= assists <= potential <= 60 and 10 <= minutes <= 60:
            rows.append(dict(date=match[1], game=f'{team_code(match[2])}@{team_code(match[3])}',
                             name=name, rounded_minutes=minutes, assists=assists, rebounds=rebounds,
                             potential=potential))
    return rows


def tracked_box_rows(scheduled, track, traditional):
    """Join official final tracking and counting boxes by exact identity and minutes."""
    day, game_id, away, home = scheduled
    track, box = track['boxScorePlayerTrack'], traditional['boxScoreTraditional']
    if track['gameId'] != game_id or box['gameId'] != game_id:
        raise ValueError('Tracking and traditional boxes must match the scheduled game ID.')
    rows = []
    for side, club in [('awayTeam', away), ('homeTeam', home)]:
        tracking, counts = track[side], box[side]
        if (tracking['teamId'] != counts['teamId']
                or any(team_code(team['teamTricode']) != team_code(club) for team in (tracking, counts))):
            raise ValueError('Tracking and traditional teams must match the schedule.')
        by_id = {p['personId']: p for p in tracking['players']}
        if len(by_id) != len(tracking['players']) or len({p['personId'] for p in counts['players']}) != len(counts['players']):
            raise ValueError('Ambiguous player IDs in official boxes.')
        for player in counts['players']:
            pid, stats = player['personId'], player['statistics']
            observed = by_id.get(pid, {}).get('statistics', {})
            minutes = played_minutes(stats.get('minutes'))
            if minutes is None or minutes < 10 or minutes != played_minutes(observed.get('minutes')):
                continue
            rebounds, assists = stats.get('reboundsTotal'), stats.get('assists')
            chances = observed.get('reboundChancesTotal')
            valid = (type(rebounds) is int and type(chances) is int and 0 <= rebounds <= chances <= 70)
            if type(assists) is not int or type(rebounds) is not int:
                continue
            shot_counts = [observed.get(key) for key in
                           ('contestedFieldGoalsAttempted', 'uncontestedFieldGoalsAttempted',
                            'contestedFieldGoalsMade', 'uncontestedFieldGoalsMade')]
            field_goals, shots = stats.get('fieldGoalsMade'), stats.get('fieldGoalsAttempted')
            shooting = (all(type(value) is int and 0 <= value <= 70 for value in [*shot_counts, shots, field_goals])
                        and shot_counts[2] <= shot_counts[0] and shot_counts[3] <= shot_counts[1]
                        and sum(shot_counts[:2]) == shots and sum(shot_counts[2:]) == field_goals)
            name = player_key(f"{player['firstName']} {player['familyName']}")
            rows.append(dict(date=day, game_id=game_id, game=f'{team_code(away)}@{team_code(home)}',
                             team=team_code(club), nba_id=str(pid), name=name, minutes=minutes,
                             rounded_minutes=int(minutes+.5), rebounds=rebounds, assists=assists,
                             field_goals=field_goals if shooting else None, shots=shots if shooting else None,
                             contested_shots=shot_counts[0] if shooting else None,
                             rebound_chances=chances if valid else None))
    return rows


def join_assist_tracking(official, passing):
    """Require a unique provider name, oriented game, date and box-count agreement."""
    keys = ['name', 'game', 'date']
    passing = passing.drop_duplicates(keys, keep=False)
    exact = official.loc[~official.duplicated(keys, keep=False)].merge(
        passing, on=[*keys, 'rounded_minutes', 'assists', 'rebounds'], validate='one_to_one')
    return official.merge(exact[['game_id', 'nba_id', 'potential']],
                          on=['game_id', 'nba_id'], how='left', validate='one_to_one')


def compare_tracking_conversion(records, schedule, *, channel):
    """Vary opportunity frequency and conversion individually on identical players."""
    outcome, chances = {'rebounds': ('rebounds', 'rebound_chances'),
                        'assists': ('assists', 'potential'),
                        'field_goals': ('field_goals', 'shots')}[channel]
    rows = _scheduled_player_rows(records, schedule)
    rows = rows.loc[rows[chances].notna()]
    daily = rows.groupby('date')[[outcome, chances]].sum()
    preceding = daily.cumsum() - daily
    result = []
    for _, group in rows.groupby(['nba_id', 'team']):
        ordered = group.sort_values('sequence').to_dict('records')
        for i in range(4, len(ordered)):
            prior, target = ordered[i-4:i], ordered[i]
            seq = target['sequence']
            if [row['sequence'] for row in prior] != list(range(seq-4, seq)):
                continue
            total = sum(row[chances] for row in prior)
            day = target['date']
            earlier = preceding.loc[day]
            if total < 4 or earlier[chances] < 20:
                continue
            prior_count = sum(row[outcome] for row in prior)
            personal_rate = prior_count/total
            cohort_rate = earlier[outcome]/earlier[chances]
            shrunk_rate = (prior_count+20*cohort_rate)/(total+20)
            minutes = sum(row['minutes'] for row in prior)/4
            recent = prior[-2:]
            recent_chances = sum(row[chances] for row in recent)/sum(row['minutes'] for row in recent)*minutes
            for policy, opportunity, conversion in [
                ('Four-game outcome average', total/4, personal_rate),
                ('Recent opportunity rate', recent_chances, personal_rate),
                ('Pooled conversion', total/4, shrunk_rate),
                ('Recent opportunities and pooled conversion', recent_chances, shrunk_rate),
            ]:
                prediction = opportunity*conversion
                result.append(dict(date=day, game_id=target['game_id'], nba_id=target['nba_id'],
                                   team=target['team'], policy=policy, outcome=target[outcome],
                                   prediction=prediction, absolute_error=abs(prediction-target[outcome]),
                                   opportunities_error=abs(opportunity-target[chances])))
    return pd.DataFrame(result)
