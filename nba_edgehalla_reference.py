"""Read the public Edgehalla minutes board as an advisory NBA reference."""
import re

from bs4 import BeautifulSoup

from nba_distribution_review import bounded, timestamp
from opportunity_evidence import FD_WEIGHTS
from slate_import import player_key, team_code

URL = 'https://www.edgehalla.com/fantasy-basketball/projections/today/minutes'
METRICS = {'MIN': 'minutes', 'PTS': 'points', 'REB': 'rebounds', 'AST': 'assists',
           'STL': 'steals', 'BLK': 'blocks', 'TO': 'turnovers'}


def conditional_fd_points(row):
    """Translate the reference's published box components into FanDuel points."""
    return round(sum(weight * row['rebounds' if field == 'reboundsTotal' else field]
                     for field, weight in FD_WEIGHTS.items()), 2)


def edgehalla_reference(raw, slate, observed_at, schedule):
    """Keep observed values conditional on play and outside scoring consensus."""
    stamp = timestamp(observed_at)
    if stamp is None or not 0 <= (slate - stamp.tz_convert('America/New_York').date()).days <= 1:
        raise ValueError('Board date must be today or tomorrow in ET')
    games = set()
    for row in schedule:
        tip = timestamp(row.get('gameTimeUtc'))
        if (row.get('gameStatus') not in (None, 1, '1') or tip is None or tip <= stamp
                or tip.tz_convert('America/New_York').date() != slate):
            continue
        away, home = (team_code(row[side]['teamTricode']) for side in ('awayTeam', 'homeTeam'))
        if away and home and away != home:
            games.add(f'{away}@{home}')
    if not games:
        raise ValueError('No matching upcoming official games')
    soup = BeautifulSoup(raw, 'html.parser')
    heading = soup.select_one('h1')
    if heading is None or heading.get_text(' ', strip=True) != f'NBA Minutes Projections: {slate:%A, %B} {slate.day}':
        raise ValueError('Wrong or unavailable Edgehalla slate date')
    rows = {}
    ambiguous = set()
    for table in soup.select('table'):
        headers = [th.get_text(' ', strip=True) for th in table.select('thead th')]
        if len(set(headers)) != len(headers) or not {'Player', 'Game', *METRICS} <= set(headers):
            continue
        for tr in table.select('tbody tr'):
            cells = tr.find_all(['th', 'td'], recursive=False)
            if len(cells) != len(headers):
                continue
            cols = dict(zip(headers, cells))
            link = cols['Player'].select_one('a[href^="/nba/players/"]')
            team_label = cols['Player'].select_one('span')
            if link is None or team_label is None:
                continue
            team = team_code(team_label.get_text(' ', strip=True).split('·')[0])
            matchup = re.fullmatch(r'(@|vs)\s*([A-Z]{2,3})', cols['Game'].get_text(' ', strip=True))
            player = link.get_text(' ', strip=True)
            if not matchup or not team or not player_key(player):
                continue
            opponent = team_code(matchup[2])
            game = f'{team}@{opponent}' if matchup[1] == '@' else f'{opponent}@{team}'
            if game not in games:
                continue
            values = {metric: bounded(cols[label].get_text(' ', strip=True), 0, 48 if label == 'MIN' else 100)
                      for label, metric in METRICS.items()}
            if any(value is None for value in values.values()):
                continue
            key = (player_key(player), team, game)
            if key in rows:
                ambiguous.add(key)
                continue
            rows[key] = dict(player=player, team=team, game=game, **values, source=URL,
                             source_player=link['href'], as_of=None, observed_at=stamp.isoformat(),
                             conditional_on_playing=True)
    forecasts = [row for key, row in rows.items() if key not in ambiguous]
    if not forecasts:
        raise ValueError('No verifiable public minutes rows')
    return forecasts
