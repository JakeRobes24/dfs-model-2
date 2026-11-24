"""Point-in-time research for a reconciled NBA pool. Network sources fail independently."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
import json
import re
from urllib.parse import unquote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber

from model import consensus, norm
from prelock import REQUIRED, OFFICIAL_STATUS, apply_prelock, review_prelock_evidence
from slate_import import contest_player_keys, matchup_key, player_key, team_code


ET = ZoneInfo('America/New_York')
INJURY_INDEX = 'https://www.nba.com/players/injury-report'
INJURY_HOST = 'https://ak-static.cms.nba.com'
NBA_WEB = 'https://www.nba.com'
RW_LINEUPS = 'https://www.rotowire.com/basketball/nba-lineups.php'
RW_MINUTES = 'https://www.rotowire.com/basketball/projected-minutes.php'
DFF = 'https://www.dailyfantasyfuel.com/nba/projections/fanduel/'
REPORT_FILENAME = re.compile(r'/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{1,2}_\d{2}[AP]M)\.pdf$')
GAME_ID = re.compile(r'\d{10}')
STATUS = re.compile(r'^(out|available|probable|questionable|doubtful)\b', re.I)
HISTORY_COLUMNS = ['player', 'season_mpg', 'last5_mpg', 'last10_mpg',
                   'history_games', 'history_latest', 'history_source', 'recent_starts']


def fetch(url):
    request = Request(url, headers={'User-Agent': 'DFS Model 2.0 research (+public NBA data)'})
    with urlopen(request, timeout=5) as response:
        data = response.read(6 * 1024 * 1024 + 1)
    if len(data) > 6 * 1024 * 1024:
        raise ValueError('Research response exceeds size limit')
    return data


def report_links(html, slate, as_of):
    soup = BeautifulSoup(html, 'html.parser')
    reports = []
    for link in soup.find_all('a', href=True):
        url = unquote(link['href'])
        if url.startswith('/referee/'):
            url = INJURY_HOST + url
        if not url.startswith(INJURY_HOST + '/'):
            continue
        match = REPORT_FILENAME.search(url)
        if not match:
            continue
        stamp = datetime.strptime(' '.join(match.groups()), '%Y-%m-%d %I_%M%p').replace(tzinfo=ET)
        if slate - timedelta(days=1) <= stamp.date() <= slate and stamp <= as_of:
            reports.append((stamp, url))
    return sorted(set(reports), reverse=True)


def injury_records(document, slate, as_of, source):
    # The PDF carries game date/team across sparsely repeated rows and continuation pages.
    game_date, game, team = None, '', ''
    records, bounds = [], None
    with pdfplumber.open(BytesIO(document)) as pdf:
        for page in pdf.pages:
            lines = page.extract_text_lines(layout=False, x_tolerance=.65)
            header = next((line for line in lines if 'Player Name' in line['text']
                           and 'Current Status' in line['text']), None)
            words = page.extract_words(x_tolerance=.65)
            if header is not None:
                starts = {word['text']: word['x0'] for word in words if abs(word['top'] - header['top']) < 2}
                if {'Matchup', 'Team', 'Player', 'Current', 'Reason'} <= starts.keys():
                    bounds = [starts[key] - 3 for key in ('Matchup', 'Team', 'Player', 'Current', 'Reason')]
            if bounds is None:
                continue
            for line in lines:
                if header is not None and line['top'] <= header['top']:
                    continue
                columns = [''] * 6
                for word in words:
                    if abs(word['top'] - line['top']) < 2:
                        index = sum(word['x0'] >= bound for bound in bounds)
                        columns[index] = (columns[index] + ' ' + word['text']).strip()
                timing, matchup, club, name, status, _ = columns
                match_date = re.search(r'\d{2}/\d{2}/\d{4}', timing)
                if match_date:
                    game_date = datetime.strptime(match_date[0], '%m/%d/%Y').date()
                    game, team = '', ''
                if '@' in matchup:
                    game = '@'.join(team_code(code) for code in matchup.split('@'))
                    team = ''
                if club:
                    code = team_code(club.replace(' NOT YET SUBMITTED', '').replace(' NONE', ''))
                    team = code
                status = STATUS.match(status)
                if game_date != slate or not team or team not in game.split('@') or not status or ',' not in name:
                    continue
                last, first = name.split(',', 1)
                records.append(dict(player=f'{first.strip()} {last.strip()}', team=team, game=game,
                                    source=source, independent_group='nba', observed_at=as_of.isoformat(),
                                    official=True, status=status[1].lower(), starter='', role='', minutes=None))
    return records


def league_injuries(slate, as_of):
    reports = report_links(fetch(INJURY_INDEX), slate, as_of)
    if not reports:
        raise ValueError('No dated NBA injury report found')
    stamp, url = reports[0]
    rows = injury_records(fetch(url), slate, stamp, url)
    return rows, f'{len(rows)} entries · issued {stamp:%b %d %I:%M %p ET}'


def nba_page(url):
    data = BeautifulSoup(fetch(url), 'html.parser').select_one('#__NEXT_DATA__')
    if data is None or not data.string:
        raise ValueError('NBA page has no structured data')
    return json.loads(data.string)['props']['pageProps']


def games_for_date(day):
    data = nba_page(f'{NBA_WEB}/games?date={day}')
    if data['selectedDate'] != day.isoformat():
        raise ValueError('NBA schedule returned a different date')
    return [card['cardData'] for module in data['gameCardFeed']['modules']
            for card in module.get('cards', []) if card.get('cardData', {}).get('gameId')]


def played_minutes(value):
    match = re.fullmatch(r'(\d{1,2}):(\d{2})', str(value))
    if not match or int(match[2]) >= 60:
        return None
    minutes = int(match[1]) + int(match[2]) / 60
    return minutes if 0 < minutes <= 60 else None


def rotation_box_details(players, inactives):
    """Capture only explicit participation and absences from a final team box."""
    identities: dict[str, set[str]] = {}
    played, absent = set(), set()
    for roster, inactive in ((players, False), (inactives, True)):
        for player in roster:
            name = f"{player.get('firstName', '')} {player.get('familyName', '')}".strip()
            if not name or not player.get('personId'):
                continue
            key = player_key(name)
            identities.setdefault(key, set()).add(str(player['personId']))
            if inactive or re.match(r'^DNP\b', str(player.get('comment', '')), re.I):
                absent.add(key)
            if not inactive and played_minutes((player.get('statistics') or {}).get('minutes')):
                played.add(key)
    ambiguous = {key for key, ids in identities.items() if len(ids) != 1}
    return played - ambiguous, absent - played - ambiguous


def read_box(game, url):
    away, home = (game[key] for key in ('awayTeam', 'homeTeam'))
    game_code = f"{team_code(away['teamTricode'])}@{team_code(home['teamTricode'])}"
    rows = []
    game_day = pd.to_datetime(game.get('gameTimeUTC'), utc=True, errors='coerce')
    if pd.isna(game_day) or game.get('gameStatus') != 3:
        return rows
    for club in (away, home):
        team = team_code(club['teamTricode'])
        players = club.get('players', [])
        played, absent = rotation_box_details(players, club.get('inactives', []))
        for player in players:
            name = f"{player.get('firstName', '')} {player.get('familyName', '')}".strip()
            stats = player.get('statistics') or {}
            minutes = played_minutes(stats.get('minutes'))
            if name and minutes:
                rows.append(dict(player=name, team=team, game=game_code, minutes=minutes,
                                 game_date=game_day.tz_convert(ET).date(),
                                 started=str(player['starter']) == '1' if 'starter' in player else None,
                                 nba_id=str(player.get('personId') or ''), source=url,
                                 teammates_played=tuple(sorted(played)), teammates_absent=tuple(sorted(absent)),
                                 **{key: stats.get(key) for key in ('points', 'reboundsTotal', 'assists',
                                     'steals', 'blocks', 'turnovers', 'fieldGoalsAttempted', 'freeThrowsAttempted')}))
    return rows


def recent_boxscores(slate, games, *, game_limit=3, days_back=7):
    teams = {team for game in games for team in game.split('@')}
    previous = {team: [] for team in teams}
    schedule_loaded = 0

    def dates(day):
        try:
            return games_for_date(day), True
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return [], False

    def load(item):
        day, game_id, away, home = item
        url = f'{NBA_WEB}/game/{away.lower()}-vs-{home.lower()}-{game_id}/box-score'
        try:
            game = nba_page(url)['game']
            if game.get('gameId') != game_id:
                return []
            return [row for row in read_box(game, url) if row['game_date'] == day]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return []

    with ThreadPoolExecutor(max_workers=12) as workers:
        days = [slate - timedelta(days=index) for index in range(1, days_back + 1)]
        for day, (entries, ok) in zip(days, workers.map(dates, days)):
            schedule_loaded += int(ok)
            for game in entries:
                away, home = [team_code(game[key]['teamTricode']) for key in ('awayTeam', 'homeTeam')]
                game_id = str(game['gameId'])
                if not away or not home or game.get('gameStatus') != 3 or not GAME_ID.fullmatch(game_id):
                    continue
                for team in {away, home} & teams:
                    if len(previous[team]) < game_limit:
                        previous[team].append((day, game_id, away, home))
        scheduled = sorted({game for rows in previous.values() for game in rows})
        responses = list(workers.map(load, scheduled))
    return [row for rows in responses for row in rows], (
        f'{sum(bool(rows) for rows in responses)}/{len(scheduled)} final box scores · '
        f'{schedule_loaded}/{len(days)} dated schedule pages reached'
    )


def rotowire_research(slate, as_of):
    if slate != as_of.astimezone(ET).date():
        raise ValueError('Live starters require today’s slate')
    lineups = BeautifulSoup(fetch(RW_LINEUPS), 'html.parser')
    main = lineups.select_one('main[data-gamedate]')
    if main is None or main['data-gamedate'] != slate.isoformat():
        raise ValueError('RotoWire returned a different slate')
    notes, pretip_teams = [], {}
    for game in main.select('.lineup.is-nba'):
        tip = game.select_one('.lineup__time')
        stamp = re.fullmatch(r'(\d{1,2}:\d{2} [AP]M) ET', tip.get_text(strip=True)) if tip else None
        if not stamp or datetime.combine(slate, datetime.strptime(stamp[1], '%I:%M %p').time(), ET) <= as_of:
            continue
        teams = []
        for side in ('is-visit', 'is-home'):
            club = game.select_one(f'.lineup__team.{side} img[alt]')
            teams.append(team_code(club['alt']) if club else '')
        if not all(teams):
            continue
        matchup = '@'.join(teams)
        for team, side in zip(teams, ('is-visit', 'is-home')):
            pretip_teams[team] = matchup
            roster = game.select_one(f'.lineup__list.{side}')
            declared = roster.select_one('.lineup__status.is-confirmed') if roster else None
            if declared is None:
                continue
            starters = []
            for row in roster.find_all('li', recursive=False):
                if 'lineup__title' in row.get('class', []) or row.select_one('button'):
                    break
                player = row.select_one('.lineup__pos + a[title]')
                if player:
                    starters.append(player['title'])
            if len(set(starters)) == len(starters) == 5:
                notes.extend(dict(player=name, team=team, game=matchup, source=RW_LINEUPS,
                                  independent_group='rotowire', observed_at=as_of.isoformat(), official=True,
                                  status='', starter='starter', role='', minutes=None) for name in starters)

    try:
        minutes_page = BeautifulSoup(fetch(RW_MINUTES), 'html.parser')
    except OSError:
        return notes, f'{len(notes)} starters reported confirmed · public minutes unavailable'
    minutes_count = 0
    for club in minutes_page.select('.proj-min-box'):
        logo = club.select_one('.lineup__team img[alt]')
        team = team_code(logo['alt']) if logo else ''
        if team not in pretip_teams:
            continue
        for row in club.select('.lineups-viz__player'):
            player = row.select_one('.lineups-viz__player-name a')
            mins = row.select_one('[data-proj]')
            group = row.parent.parent.select_one('.lineups-viz__title')
            if player is None or mins is None or group is None or not re.fullmatch(r'\d{1,2}', mins['data-proj']):
                continue
            minutes = int(mins['data-proj'])
            label = group.get_text(strip=True).lower()
            if not 0 < minutes <= 48 or label not in {'starters', 'bench'}:
                continue
            notes.append(dict(player=player.get_text(strip=True), team=team, game=pretip_teams[team],
                              source=RW_MINUTES, independent_group='rotowire', observed_at=as_of.isoformat(),
                              official=False, status='', starter='',
                              role='Projected starter' if label == 'starters' else 'Projected bench',
                              minutes=minutes))
            minutes_count += 1
    return notes, f'{sum(bool(row["starter"]) for row in notes)} starters reported confirmed · {minutes_count} public minutes estimates'


def dff_projections(slate, as_of):
    soup = BeautifulSoup(fetch(DFF), 'html.parser')
    html_text = soup.get_text(' ', strip=True)
    match = re.search(r'Updated At:\s*([A-Z][a-z]{2}, [A-Z][a-z]{2} \d+, \d{4}, \d{1,2}:\d{2} [AP]M) ET', html_text, re.I)
    if not match:
        raise ValueError('Independent projection update time unavailable')
    stamp = datetime.strptime(match[1], '%a, %b %d, %Y, %I:%M %p').replace(tzinfo=ET)
    if stamp.date() != slate or not as_of - timedelta(hours=6) <= stamp <= as_of:
        raise ValueError('Independent projections are stale or for another day')
    rows = []
    for row in soup.select('tr.projections-listing[data-start_date][data-ppg_proj]'):
        if row['data-start_date'] != slate.isoformat():
            continue
        team, opponent = [team_code(row.get(key, '')) for key in ('data-team', 'data-opp')]
        points = row['data-ppg_proj']
        name = row.get('data-name', '')
        if not (name and team and opponent and re.fullmatch(r'\d+(?:\.\d+)?', points)):
            continue
        rows.append(dict(player=name, team=team, game=f'{team}@{opponent}', points=float(points),
                         source=DFF, observed_at=stamp.isoformat()))
    if not rows:
        raise ValueError('Public projection table unavailable')
    return rows, f'{len(rows)} public projections · updated {stamp:%I:%M %p ET}'


PROPSIMS = 'https://propsims.com/nba/dfs/'


def propsims_research(slate, as_of):
    soup = BeautifulSoup(fetch(PROPSIMS), 'html.parser')
    heading = soup.select_one('h1')
    clock = soup.select_one('.updstamp time[datetime]')
    if heading is None or clock is None or not heading.get_text(strip=True).endswith(
        f'{slate:%A, %B} {slate.day}'
    ):
        raise ValueError('PropSims slate date unavailable')
    stamp = datetime.fromisoformat(clock['datetime']).astimezone(ET)
    if stamp.date() != slate or not as_of - timedelta(hours=6) <= stamp <= as_of:
        raise ValueError('PropSims projections are stale')
    notes, projections = [], []
    for cell in soup.select('td[data-f="fd_p50"][data-v]'):
        row = cell.find_parent('tr')
        name = row.select_one('.player a')
        matchup = row.select_one('.player .msub')
        minutes_cell = row.select_one('td[data-f="min_p50"][data-v]')
        if name is None or matchup is None or minutes_cell is None:
            continue
        match = re.fullmatch(r'([A-Z]{2,3})\s*·.*?\s+(?:vs|@)\s+([A-Z]{2,3})', matchup.get_text(strip=True).removesuffix(' · not on main slate'))
        if not match:
            continue
        team, opponent = map(team_code, match.groups())
        points, minutes = float(cell['data-v']), float(minutes_cell['data-v'])
        if not team or not opponent or team == opponent or not (0 <= points <= 150 and 0 <= minutes <= 60):
            continue
        common = dict(player=name.get_text(strip=True), team=team, game=f'{team}@{opponent}',
                      source=PROPSIMS, observed_at=stamp.isoformat())
        projections.append(dict(common, points=points))
        notes.append(dict(common, independent_group='propsims', official=False, status='',
                          starter='', role='', minutes=minutes))
    if not projections:
        raise ValueError('PropSims FanDuel table unavailable')
    return (notes, projections), f'{len(projections)} minutes and FanDuel estimates · updated {stamp:%I:%M %p ET}'


ROTOGRINDERS = 'https://rotogrinders.com/projected-stats/nba'


def rotogrinders_research(slate, as_of):
    soup = BeautifulSoup(fetch(ROTOGRINDERS), 'html.parser')
    label = soup.find(string=lambda value: value and value.strip() == 'FPTS Updated')
    clock = label.parent.parent.select_one('[data-role="localtime"][data-value]') if label else None
    if clock is None:
        raise ValueError('RotoGrinders update time unavailable')
    stamp = datetime.fromisoformat(clock['data-value']).astimezone(ET)
    if stamp.date() != slate or not as_of - timedelta(hours=6) <= stamp <= as_of:
        raise ValueError('RotoGrinders estimates are stale')
    games = {}
    for item in soup.select('[data-field="schedule"][data-value]'):
        match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}) (\d{1,2}:\d{2}[ap]m) \(([A-Z]+) @ ([A-Z]+)\)',
                             item.get_text(strip=True), re.I)
        if not item['data-value'].isdigit() or not match or match[1] != slate.isoformat():
            continue
        tip = datetime.strptime(f'{match[1]} {match[2]}', '%Y-%m-%d %I:%M%p').replace(tzinfo=ET)
        if as_of < tip:
            games[item['data-value']] = tuple(map(team_code, match.groups()[2:]))
    notes, projections = [], []
    weights = {'PTS': 1, 'REB': 1.2, 'AST': 1.5, 'STL': 3, 'BLK': 3, 'TO': -1}
    for table in soup.select('table'):
        columns = [heading.get_text(strip=True) for heading in table.select('thead th')]
        if not {'TEAM', 'OPP', 'MINUTES', *weights}.issubset(columns):
            continue
        for row in table.select('tbody tr[data-schedule]'):
            matchup = games.get(row['data-schedule'])
            cells = [cell.get_text(strip=True) for cell in row.find_all('td', recursive=False)]
            name = row.select_one('a[data-role="modal"]')
            if not matchup or not name or len(cells) != len(columns):
                continue
            fields = dict(zip(columns, cells))
            team, opponent = map(team_code, (fields['TEAM'], fields['OPP']))
            if not team or not opponent or {team, opponent} != set(matchup):
                continue
            try:
                minutes = float(fields['MINUTES'])
                stats = {key: float(fields[key]) for key in weights}
            except ValueError:
                continue
            if not 0 <= minutes <= 48 or not all(0 <= value <= 150 for value in stats.values()):
                continue
            common = dict(player=name.get_text(strip=True), team=team, game='@'.join(matchup),
                          source=ROTOGRINDERS, observed_at=stamp.isoformat())
            notes.append(dict(common, independent_group='rotogrinders', official=False,
                              status='', starter='', role='', minutes=minutes))
            projections.append(dict(common, points=round(sum(stats[key] * weight for key, weight in weights.items()), 2)))
    if not notes:
        raise ValueError('No verifiable public RotoGrinders estimates for upcoming games')
    return (notes, projections), f'{len(notes)} pre-tip estimates · updated {stamp:%I:%M %p ET}'


NBA_HOUSE = 'https://nbahouse.net/minutes'


def nba_house_minutes(slate, as_of):
    soup = BeautifulSoup(fetch(NBA_HOUSE), 'html.parser')
    heading = soup.select_one('.minutes-page h1')
    if heading is None or datetime.strptime(heading.get_text(strip=True), '%A %d %B %Y').date() != slate:
        raise ValueError('NBA House slate date unavailable')
    notes = []
    for card in soup.select('article.mins-card[id]'):
        away, sep, home = card['id'].partition('-at-')
        away, home = team_code(away), team_code(home)
        clock = card.select_one('header time[datetime]')
        if not sep or not away or not home or not clock:
            continue
        tip = datetime.fromisoformat(clock['datetime']).astimezone(ET)
        if tip.date() != slate or not as_of < tip:
            continue
        for side in card.select('.mins-team[data-mins-side]'):
            team = {'away': away, 'home': home}.get(side['data-mins-side'])
            if not team:
                continue
            for row in side.select('table.mins-table tbody tr'):
                player, estimate = row.select_one('.nm-t'), row.select_one('.mproj b')
                if player is None or estimate is None or not estimate.get_text(strip=True).isdigit():
                    continue
                minutes = int(estimate.get_text(strip=True))
                if 0 <= minutes <= 48:
                    notes.append(dict(player=player.get_text(strip=True), team=team, game=f'{away}@{home}',
                                      source=NBA_HOUSE, observed_at=as_of.isoformat(), independent_group='nba-house',
                                      official=False, status='', starter='', role='', minutes=minutes))
    if not notes:
        raise ValueError('No NBA House minutes for upcoming games')
    return (notes, []), f'{len(notes)} pre-tip minutes estimates · observed {as_of:%I:%M %p ET}'


LINEUPEXPERTS_TODAY = 'https://www.lineupexperts.com/basketball/projections?flt_pos=Utility&flt_proj_time_period=Today'


def lineupexperts_reference(slate, today):
    """Read public reference estimates without treating the page as a dated feed."""
    if slate != today:
        return []
    soup = BeautifulSoup(fetch(LINEUPEXPERTS_TODAY), 'html.parser')
    if not soup.title or not soup.title.get_text(strip=True).lower().endswith('for today'):
        raise ValueError('LineupExperts Today view unavailable')
    weights = {'PTS': 1, 'RB': 1.2, 'AST': 1.5, 'STL': 3, 'BLK': 3, 'TO': -1}
    records = []
    for table in soup.select('table'):
        headers = [col.get_text(' ', strip=True) for col in table.select('thead th')]
        if not {'Player', 'Game Details', *weights}.issubset(headers):
            continue
        for row in table.select('tbody tr'):
            name = row.select_one('.projectionsPlayerCell .hideForMobile')
            club = row.select_one('.projectionsPlayerCell small')
            cells = row.find_all('td', recursive=False)
            if not name or not club or len(cells) != len(headers):
                continue
            fields = dict(zip(headers, cells))
            matchup = fields['Game Details'].select_one('li')
            team = team_code(club.get_text(strip=True).strip('()').split(' - ', 1)[0])
            match = re.match(r'^(?:vs\.?|@|at)\s*([A-Z]{2,3})\b', matchup.get_text(' ', strip=True)) if matchup else None
            opponent = team_code(match[1]) if match else ''
            if not team or not opponent or team == opponent:
                continue
            try:
                stats = {key: float(fields[key].get_text(strip=True)) for key in weights}
            except ValueError:
                continue
            if all(0 <= value <= 150 for value in stats.values()):
                records.append(dict(player=name.get_text(strip=True), team=team, game=f'{team}@{opponent}',
                                    reference_fd=round(sum(stats[key] * weight for key, weight in weights.items()), 2)))
    if not records:
        raise ValueError('LineupExperts reference table unavailable')
    return records


FANTASY_SPORTS_EDGE = 'https://fantasysportsedge.com/nba/projections'


def fantasysportsedge_reference(slate, as_of):
    soup = BeautifulSoup(fetch(FANTASY_SPORTS_EDGE), 'html.parser')
    match = re.search(r'Projections updated ([A-Za-z]+ \d{1,2}, \d{4}) at (\d{1,2}:\d{2} [AP]M) (E[DS]T)',
                      soup.get_text(' ', strip=True))
    if not match:
        raise ValueError('FantasySportsEdge update time unavailable')
    stamp = datetime.strptime(f'{match[1]} {match[2]}', '%B %d, %Y %I:%M %p').replace(tzinfo=ET)
    if stamp.date() != slate or stamp > as_of or stamp.tzname() != match[3]:
        raise ValueError('FantasySportsEdge is for a different slate date')
    records = []
    required = {'Player', 'Team', 'Opp', 'FD Salary', 'Projection'}
    for table in soup.select('table'):
        headers = [col.get_text(' ', strip=True) for col in table.select('thead th')]
        if not required.issubset(headers):
            continue
        for row in table.select('tbody tr'):
            cells = [c.get_text(' ', strip=True) for c in row.find_all('td', recursive=False)]
            if len(cells) != len(headers):
                continue
            data = dict(zip(headers, cells))
            team, opponent = map(team_code, (data['Team'], data['Opp']))
            try:
                salary = int(data['FD Salary'].replace('$', '').replace(',', ''))
                points = float(data['Projection'])
            except ValueError:
                continue
            if team and opponent and team != opponent and 0 < salary <= 60000 and 0 <= points <= 150:
                records.append(dict(player=data['Player'], team=team, game=f'{team}@{opponent}',
                                    reference_salary=salary, reference_points=points))
    return records, stamp


FTA_NBA_BOARD = 'https://fantasyteamadvisors.com/nba-dfs-draftkings-projections/?site=fd'
FTA_NBA_PREVIEW = (
    'https://fantasyteamadvisors.com/wp-admin/admin-ajax.php'
    '?action=fta_data&tool=fta-nba-projections&f=nba-slate-data.json'
)


def fta_nba_reference(slate, as_of, contest_games):
    """Read the same public preview as the NBA board and require an exact game set."""
    data = json.loads(fetch(FTA_NBA_PREVIEW))
    if data.get('date') != slate.isoformat() or data.get('preview') is not True:
        raise ValueError('Fantasy Team Advisors public preview is unavailable for this date')
    prefix = f'{slate:%b} {slate.day}, '
    generated = data['generated']
    if not generated.startswith(prefix) or not generated.endswith(' ET'):
        raise ValueError('Fantasy Team Advisors update time unavailable')
    clock = datetime.strptime(generated[len(prefix):-3], '%I:%M %p').time()
    stamp = datetime.combine(slate, clock, ET)
    if not as_of - timedelta(hours=6) <= stamp <= as_of:
        raise ValueError('Fantasy Team Advisors estimates are stale')
    columns = data['cols']
    required = {'n', 'team', 'opp', 'sal', 'proj', 'min', 'own', 'p85'}
    if not required.issubset(columns) or len(set(columns)) != len(columns):
        raise ValueError('Fantasy Team Advisors preview format changed')
    candidates = []
    expected = {matchup_key(game) for game in contest_games}
    for board in data['slates']:
        if board.get('site') != 'FanDuel' or board.get('games') != len(expected):
            continue
        rows = [dict(zip(columns, row)) for row in board['rows'] if len(row) == len(columns)]
        games = {matchup_key(f"{team_code(row['team'])}@{team_code(row['opp'])}") for row in rows}
        if games == expected:
            candidates.append((board, rows))
    if len(candidates) != 1:
        raise ValueError('No unique FanDuel slate matched the contest game set')
    board, rows = candidates[0]
    records = []
    for row in rows:
        def bounded(key, limit):
            value = row[key]
            return value if type(value) in (int, float) and 0 <= value <= limit else None

        team, opponent = team_code(row['team']), team_code(row['opp'])
        records.append(dict(player=row['n'], team=team, game=f'{team}@{opponent}',
                            reference_salary=bounded('sal', 60000), reference_points=bounded('proj', 150),
                            reference_minutes=bounded('min', 60),
                            reference_ownership=bounded('own', 100) if board.get('hasOwn') is True else None,
                            reference_ceiling=bounded('p85', 200)))
    return records, stamp, board['label'], board.get('total', len(records))


def compare_reference(pool, records):
    matches = pd.DataFrame(match_public(pool, records))
    if matches.empty:
        return matches
    columns = ['fanduel_id', 'fanduel_name', 'salary', 'eligible', 'projected_fd_points',
               'adjusted_fd_points', 'adjusted_minutes']
    compared = pool[columns].merge(matches.drop_duplicates('fanduel_id', keep=False),
                                   on='fanduel_id', validate='one_to_one')
    compared = compared.loc[compared.salary.eq(compared.reference_salary) & compared.eligible].copy()
    compared['points_gap'] = (compared.reference_points - compared.adjusted_fd_points).round(2)
    compared['research_check'] = ''
    missing = ~compared.projected_fd_points.gt(0) & compared.reference_points.gt(0)
    compared.loc[missing, 'research_check'] = 'Missing DAILY projection'
    compared.loc[~missing & compared.points_gap.abs().ge(5), 'research_check'] = 'Review points gap'
    compared.loc[~missing & compared.points_gap.abs().le(3) & compared.adjusted_fd_points.gt(0)
                 & compared.reference_points.gt(0), 'research_check'] = 'Supports model estimate'
    if 'reference_minutes' in compared:
        compared['minutes_gap'] = (compared.reference_minutes - compared.adjusted_minutes).round(2)
        minute_gap = compared.minutes_gap.abs().ge(4)
        compared.loc[minute_gap, 'research_check'] = compared.loc[minute_gap, 'research_check'].apply(
            lambda label: f'{label} · Review minutes gap' if label else 'Review minutes gap')
    return compared


def get_public_research(slate, as_of):
    """Return evidence plus report-level status. Never infer an injury from an absent row."""
    jobs = [('NBA injury report', lambda: league_injuries(slate, as_of), []),
            ('RotoWire starters and minutes', lambda: rotowire_research(slate, as_of), []),
            ('Daily Fantasy Fuel', lambda: dff_projections(slate, as_of), []),
            ('PropSims', lambda: propsims_research(slate, as_of), ([], [])),
            ('RotoGrinders', lambda: rotogrinders_research(slate, as_of), ([], [])),
            ('NBA House projected minutes', lambda: nba_house_minutes(slate, as_of), ([], []))]
    results, status = [], []
    with ThreadPoolExecutor(max_workers=len(jobs)) as workers:
        futures = [workers.submit(job) for _, job, _ in jobs]
        for (label, _, empty), future in zip(jobs, futures):
            try:
                data, detail = future.result()
            except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
                data, detail = empty, 'Unavailable for this slate or source format changed'
            results.append(data)
            status.append((label, detail))
    injuries, starters, projections, *additional = results
    for minutes, points in additional:
        starters.extend(minutes)
        projections.extend(points)
    return injuries + starters, projections, status


def match_public(pool, records):
    identities = {}
    for row in pool.itertuples():
        for name in contest_player_keys(row.fanduel_name, row.fanduel_id):
            key = (name, row.team, matchup_key(row.game))
            identities.setdefault(key, []).append(row.fanduel_id)
    matched = []
    for row in records:
        key = (player_key(row['player']), row['team'], matchup_key(row['game']))
        ids = identities.get(key, [])
        if len(ids) == 1:
            matched.append(dict(row, fanduel_id=ids[0]))
    return matched


def historical_context(pool, verified, rotations, slate):
    archive = verified.copy()
    if not archive.empty:
        archive['day'] = pd.to_datetime(archive.slate_date, errors='coerce').dt.date
        archive['minutes'] = pd.to_numeric(archive.get('official_minutes', archive.actual_minutes), errors='coerce')
        archive['minutes'] = archive.minutes.where(archive.minutes.notna(), pd.to_numeric(archive.actual_minutes, errors='coerce'))
        archive['suffix'] = archive.fanduel_id.str.extract(r'^\d+-(\d+)$')[0]
        archive['name_key'] = archive.name.map(player_key)
    identities = [contest_player_keys(row.fanduel_name, row.fanduel_id) for row in pool.itertuples()]
    name_counts = Counter(name for keys in identities for name in keys)
    records = []
    for player, keys in zip(pool.itertuples(), identities):
        if any(name_counts[key] > 1 for key in keys):
            continue
        logs = [row for row in rotations if player_key(row['player']) in keys and row['team'] == player.team
                and slate - timedelta(days=21) <= row['game_date'] < slate and row['nba_id']]
        if len({row['nba_id'] for row in logs}) > 1:
            logs = []
        samples = {row['game_date']: row['minutes'] for row in logs}
        sources = ['NBA official box scores'] if logs else []
        if not archive.empty:
            same_suffix = archive[archive.suffix.eq(player.fanduel_id.rsplit('-', 1)[-1]) & archive.day.lt(slate)]
            # Reuse matching evidence only. Any conflicting archived name vetoes the suffix.
            if len(same_suffix) and same_suffix.name_key.isin(keys).all():
                verified_minutes = same_suffix[same_suffix.minutes.between(1, 60)]
                for day, values in verified_minutes.groupby('day').minutes:
                    if day >= slate - timedelta(days=21) and values.nunique() == 1 and day not in samples:
                        samples[day] = values.iloc[0]
                        if 'Verified private history' not in sources:
                            sources.append('Verified private history')
        if samples:
            dates = sorted(samples)
            mean = sum(samples[day] for day in dates[-3:]) / min(3, len(dates))
            records.append(dict(player=player.fanduel_name, season_mpg=None, last5_mpg=None, last10_mpg=None,
                                history_games=len(samples), history_latest=dates[-1].isoformat(),
                                history_source=' + '.join(sources), recent_starts=sum(row['started'] is True for row in logs)
                                if any(row['started'] is not None for row in logs) else None, recent_mpg=mean))
    return pd.DataFrame(records, columns=HISTORY_COLUMNS + ['recent_mpg'])


POINT_SOURCE_GROUPS = {
    DFF: 'daily-fantasy-fuel', PROPSIMS: 'propsims', ROTOGRINDERS: 'rotogrinders',
    LINEUPEXPERTS_TODAY: 'lineupexperts',
}


def points_consensus(projections, evidence, as_of):
    """Weight verified point estimates by recency and count each source family once."""
    frame = pd.DataFrame(projections)
    if frame.empty:
        return pd.DataFrame(columns=['points', 'observed_at', 'source', 'source_count', 'spread', 'detail', 'inputs_json'])
    frame['family'] = frame.source.map(POINT_SOURCE_GROUPS)
    dated = frame.observed_at.astype('string').fillna('').str.strip()
    has_offset = dated.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$', regex=True)
    frame['time'] = pd.to_datetime(dated.where(has_offset), utc=True, errors='coerce', format='mixed')
    frame['points'] = pd.to_numeric(frame.points, errors='coerce')
    age = (pd.Timestamp(as_of) - frame.time).dt.total_seconds() / 3600
    frame = frame.loc[frame.family.notna() & age.between(0, 6) & frame.points.between(0, 150)].copy()
    news = pd.DataFrame(evidence)
    if not news.empty:
        affecting = news.loc[news.official.eq(True) & (
            news.status.str.casefold().isin(OFFICIAL_STATUS) |
            news.starter.isin(['starter', 'bench'])
        )].copy()
        affecting['time'] = pd.to_datetime(affecting.observed_at, utc=True, errors='coerce', format='mixed')
        newest = affecting.loc[affecting.time.le(as_of)].groupby('fanduel_id').time.max()
        if not newest.empty and not frame.empty:
            cutoff = frame.fanduel_id.map(newest)
            frame = frame.loc[cutoff.isna() | frame.time.ge(cutoff)].copy()
    frame = frame.sort_values('time')
    frame = frame.loc[~frame.duplicated(['fanduel_id', 'family', 'time'], keep=False)]
    frame = frame.drop_duplicates(['fanduel_id', 'family'], keep='last')
    frame['weight'] = 2 ** (-age.loc[frame.index] / 3)
    rows = {}
    for player, group in frame.groupby('fanduel_id'):
        rows[player] = dict(points=(group.points * group.weight).sum() / group.weight.sum(),
                            observed_at=group.time.max().isoformat(), source=', '.join(group.source),
                            source_count=len(group), spread=group.points.max() - group.points.min(),
                            detail=' · '.join(f'{row.family} {row.points:.2f}' for row in group.itertuples()),
                            inputs_json=group[['source', 'family', 'points', 'time', 'weight']]
                                .rename(columns={'time': 'observed_at'})
                                .to_json(orient='records', date_format='iso', double_precision=15))
    return pd.DataFrame.from_dict(rows, orient='index', columns=['points', 'observed_at', 'source', 'source_count', 'spread', 'detail', 'inputs_json'])


def score_slate(pool, history, evidence, projections, as_of, *, manual_minutes=None, manual_history=None):
    """Keep DAILY as the baseline and apply only bounded, corroborated changes."""
    pool = pool.copy()
    history = history.copy()
    if manual_history is not None:
        existing = {norm(name) for name in manual_history.player}
        history = pd.concat([history.loc[~history.player.map(norm).isin(existing)], manual_history], ignore_index=True)
    result = consensus(pool, manual_minutes, history)
    if 'recent_mpg' not in result:
        result['recent_mpg'] = None
    # History alone is context. A moderate, same-direction discrepancy in an independent
    # points model can support a small, explicitly provisional minutes adjustment.
    reviewed = review_prelock_evidence(pool, pd.DataFrame(evidence, columns=sorted(REQUIRED)), as_of)
    fresh = reviewed.loc[reviewed.review.eq('Reviewed')].copy()
    independent = points_consensus(projections, fresh.to_dict('records'), as_of)
    for target, field in {
        'independent_fd_points': 'points', 'independent_projection_at': 'observed_at',
        'independent_projection_source': 'source', 'projection_source_spread': 'spread',
        'projection_source_count': 'source_count', 'projection_source_estimates': 'detail',
        'projection_sources_json': 'inputs_json',
    }.items():
        result[target] = result.fanduel_id.map(independent[field])
    result['projection_source_count'] = result.projection_source_count.fillna(0).astype(int)
    result['projection_sources_json'] = result.projection_sources_json.fillna('[]')
    result['projection_scored_at_utc'] = pd.Timestamp(as_of).tz_convert('UTC').isoformat()
    result['fd_disagreement'] = result.independent_fd_points - result.projected_fd_points
    baseline, historical = result.projected_minutes, pd.to_numeric(result.recent_mpg, errors='coerce')
    minute_gap = historical - baseline
    counts = pd.to_numeric(result.get('history_games', pd.Series(0, index=result.index)), errors='coerce')
    official = fresh.loc[fresh.official & fresh.status.str.casefold().isin(OFFICIAL_STATUS)]
    newest_status = official.loc[official.observed_at.eq(official.groupby('fanduel_id').observed_at.transform('max'))]
    official_out = set(newest_status.loc[newest_status.status.str.casefold().isin(
        {'out', 'inactive', 'suspended', 'doubtful', 'questionable'}), 'fanduel_id'])
    candidates = fresh.loc[fresh.source.isin({RW_MINUTES, PROPSIMS, ROTOGRINDERS, NBA_HOUSE})
                           & fresh.minutes.notna() & fresh.independent_group.ne('')].copy()
    changes = fresh.loc[fresh.official & (fresh.status.str.casefold().isin(OFFICIAL_STATUS)
                                         | fresh.starter.str.casefold().isin({'starter', 'bench'}))]
    latest_news = changes.groupby('fanduel_id').observed_at.max()
    if not latest_news.empty and not candidates.empty:
        cutoff = candidates.fanduel_id.map(latest_news)
        candidates = candidates.loc[cutoff.isna() | candidates.observed_at.ge(cutoff)]
    groups = ['fanduel_id', 'independent_group']
    candidates = candidates.loc[candidates.observed_at.eq(candidates.groupby(groups).observed_at.transform('max'))]
    # Conflicting latest estimates from the same provider are not corroboration.
    conflicts = candidates.groupby(groups).minutes.transform('nunique').gt(1)
    conflicted_ids = set(candidates.loc[conflicts, 'fanduel_id'])
    candidates = candidates.loc[~conflicts].drop_duplicates(groups)
    by_id = candidates.groupby('fanduel_id').minutes.apply(list).to_dict()
    result['independent_minutes'] = result.fanduel_id.map(
        {key: values[0] for key, values in by_id.items() if max(values) - min(values) <= 3}
    )
    minutes_agree = ((result.independent_minutes - historical).abs().le(3)
                     & (result.independent_minutes - baseline).abs().between(2, 6))
    points_agree = (result.fd_disagreement.abs().between(2, 8)
                    & (minute_gap * result.fd_disagreement).gt(0))
    source_conflict = result.projection_source_spread.ge(5) | result.fanduel_id.isin(conflicted_ids) | result.fanduel_id.isin(
        key for key, values in by_id.items() if max(values) - min(values) > 3
    )
    corroborated = (~source_conflict & ~result.fanduel_id.isin(official_out) & result.eligible & result.minutes_method.eq('DAILY_only_unverified')
                    & counts.ge(3) & minute_gap.abs().between(2, 6) & result.fppm.gt(0)
                    & (minutes_agree | points_agree))
    result.loc[corroborated, 'adjusted_minutes'] = baseline + (minute_gap / 3).clip(-2, 2)
    result.loc[corroborated, 'adjusted_fd_points'] = result.fppm * result.adjusted_minutes
    result.loc[corroborated, 'minutes_method'] = 'provisional_corroborated_rotation'
    result.loc[corroborated, 'projection_warning'] = 'Provisional adjustment based on recent rotations and independent estimates'
    result, audit = apply_prelock(result, pd.DataFrame(evidence, columns=sorted(REQUIRED)), as_of)
    uncertain = result.prelock_status.isin(['questionable', 'doubtful']) | result.injury_flag.isin(['Q', 'D', 'GTD'])
    # Verified minutes adjustments and official scratches have priority.
    use_blend = (result.eligible & ~uncertain & ~source_conflict
                 & result.minutes_method.eq('DAILY_only_unverified')
                 & result.projection_source_count.ge(2) & result.projected_fd_points.gt(0)
                 & result.fd_disagreement.abs().lt(5))
    blend = .60 * result.projected_fd_points + .40 * result.independent_fd_points
    result['blended_fd_points'] = blend.where(use_blend)
    result.loc[use_blend, 'adjusted_fd_points'] = result.loc[use_blend, 'blended_fd_points']
    result['blend_status'] = 'Blend not verified'
    # Assign in reverse priority so every exclusion has a useful reason.
    for mask, label in [
        (use_blend, '60/40 blend applied'),
        (result.fd_disagreement.abs().ge(5), 'Independent vs DAILY disagreement'),
        (result.projection_source_count.lt(2), 'Fewer than two fresh point sources'),
        (~result.minutes_method.eq('DAILY_only_unverified'), 'Minutes/status adjustment takes priority'),
        (source_conflict, 'Independent sources disagree'),
        (uncertain, 'Availability uncertain'),
        (~result.projected_fd_points.gt(0), 'Missing DAILY baseline'),
        (~result.eligible, 'Ineligible'),
    ]:
        result.loc[mask, 'blend_status'] = label
    result['projection_method'] = 'DAILY with applicable minutes and status checks'
    result.loc[use_blend, 'projection_method'] = '60% DAILY / 40% independent blend'
    disputes = (source_conflict | result.fd_disagreement.abs().ge(5) | minute_gap.abs().gt(5)
                | (result.independent_minutes - baseline).abs().gt(5))
    result['research_attention'] = ''
    result.loc[result.prelock_starter.eq(''), 'research_attention'] += 'Starter unconfirmed. '
    result.loc[uncertain, 'research_attention'] += 'Availability uncertain. '
    result.loc[disputes, 'research_attention'] += 'Review source disagreement. '
    role_changed = result.prelock_starter.eq('starter') & result.prelock_role.eq('Projected bench')
    result.loc[role_changed, 'research_attention'] += 'Role change: confirmed starter against bench estimate. '
    result.loc[~result.adjusted_fd_points.gt(0) & result.eligible, 'research_attention'] += 'Missing usable points. '
    return result, audit
