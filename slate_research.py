"""Point-in-time research for a reconciled NBA pool. Network sources fail independently."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
import json
import re
from urllib.error import HTTPError, URLError
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


def fetch_paired_provider(url):
    """One bounded retry for transient transport/server failures only.

    Never retry access denial, rate limits, malformed data or stale forecasts.
    The provider's original timestamp must still pass its normal validation.
    """
    try:
        return fetch(url)
    except HTTPError as exc:
        if exc.code not in {500, 502, 503, 504}:
            raise
    except URLError as exc:
        if not isinstance(exc.reason, (TimeoutError, ConnectionError)):
            raise
    except (TimeoutError, ConnectionError):
        pass
    return fetch(url)


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
    from nba_matchup_context import team_box_context
    context = team_box_context(game)
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
                                 **context.get(team, {}),
                                 **{key: stats.get(key) for key in ('points', 'reboundsTotal', 'assists',
                                     'steals', 'blocks', 'turnovers', 'fieldGoalsAttempted', 'freeThrowsAttempted')}))
    return rows


def recent_boxscores(slate, games, *, game_limit=3, days_back=7, box_cache=None):
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
        if box_cache is not None:
            cached = box_cache.get(item)
            if cached is not None:
                return cached, True
        url = f'{NBA_WEB}/game/{away.lower()}-vs-{home.lower()}-{game_id}/box-score'
        try:
            game = nba_page(url)['game']
            if game.get('gameId') != game_id:
                return [], False
            rows = [row for row in read_box(game, url) if row['game_date'] == day]
            if box_cache is not None:
                box_cache.put(item, rows)
            return rows, False
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return [], False

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
    cached_count = sum(hit for _, hit in responses)
    status = (f'{sum(bool(rows) for rows, _ in responses)}/{len(scheduled)} final box scores · '
              f'{schedule_loaded}/{len(days)} dated schedule pages reached')
    if box_cache is not None:
        status += f' · {cached_count} recently verified final boxes reused'
    return [row for rows, _ in responses for row in rows], status


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



def propsims_distribution(row, median):
    """Read labeled FanDuel quantiles, not DraftKings or conditional medians."""
    table = row.find_parent('table')
    if table is None:
        return {}
    headers = [item.get_text(' ', strip=True).casefold() for item in table.select('thead th')]
    cells = row.find_all('td', recursive=False)
    if ('fd median' not in headers or len(headers) != len(cells)
            or len(set(headers)) != len(headers)):
        return {}
    fields = dict(zip(headers, cells))
    def number(label, percent=False):
        item = fields.get(label)
        if item is None:
            return None
        text = item.get_text(strip=True)
        if percent:
            if not text.endswith('%'):
                return None
            text = text[:-1]
        try:
            value = float(text)
        except ValueError:
            return None
        limit = 100 if percent else 150
        return value if 0 <= value <= limit else None

    floor, ceiling = number('floor'), number('ceiling')
    probability, conditional = number('p(play)', True), number('if plays')
    result = {}
    if floor is not None and ceiling is not None and floor <= median <= ceiling:
        result.update(fd_p10=floor, fd_p85=ceiling)
    if probability is not None:
        result['play_probability'] = probability / 100
    if conditional is not None:
        result['conditional_fd_median'] = conditional
    return result


def propsims_research(slate, as_of):
    soup = BeautifulSoup(fetch_paired_provider(PROPSIMS), 'html.parser')
    heading = soup.select_one('h1')
    clock = soup.select_one('.updstamp time[datetime]')
    if heading is None or clock is None or not heading.get_text(strip=True).endswith(
        f'{slate:%A, %B} {slate.day}'
    ):
        raise ValueError('PropSims slate date unavailable')
    # The slate heading identifies the target day; a fresh model run can
    # legitimately have been published before midnight on the preceding day.
    published = datetime.fromisoformat(clock['datetime'])
    if published.tzinfo is None or as_of.tzinfo is None:
        raise ValueError('PropSims requires timezone-aware publication and review times')
    stamp = published.astimezone(ET)
    if (slate != as_of.astimezone(ET).date()
            or stamp.date() not in {slate, slate - timedelta(days=1)}
            or not as_of - timedelta(hours=6) <= stamp <= as_of):
        raise ValueError('PropSims projections are stale or not for the current slate')
    notes, projections = [], []
    for cell in soup.select('td[data-f="fd_p50"][data-v]'):
        row = cell.find_parent('tr')
        if row is None:
            continue
        name = row.select_one('.player a')
        matchup = row.select_one('.player .msub')
        minutes_cell = row.select_one('td[data-f="min_p50"][data-v]')
        if name is None or matchup is None or minutes_cell is None:
            continue
        match = re.fullmatch(r'([A-Z]{2,3})\s*·.*?\s+(?:vs|@)\s+([A-Z]{2,3})', matchup.get_text(strip=True).removesuffix(' · not on main slate'))
        if not match:
            continue
        team, opponent = map(team_code, match.groups())
        try:
            points, minutes = float(cell['data-v']), float(minutes_cell['data-v'])
        except (ValueError, TypeError):
            continue
        if not name.get_text(strip=True) or not team or not opponent or team == opponent or not (0 <= points <= 150 and 0 <= minutes <= 60):
            continue
        common = dict(player=name.get_text(strip=True), team=team, game=f'{team}@{opponent}',
                      source=PROPSIMS, observed_at=stamp.isoformat())
        projections.append(dict(common, points=points, paired_minutes=minutes,
                                **propsims_distribution(row, points)))
        notes.append(dict(common, independent_group='propsims', official=False, status='',
                          starter='', role='', minutes=minutes))
    if not projections:
        raise ValueError('PropSims FanDuel table unavailable')
    return (notes, projections), f'{len(projections)} minutes and FanDuel estimates · updated {stamp:%I:%M %p ET}'


ROTOGRINDERS = 'https://rotogrinders.com/projected-stats/nba'


def rotogrinders_research(slate, as_of):
    soup = BeautifulSoup(fetch_paired_provider(ROTOGRINDERS), 'html.parser')
    label = soup.find(string=lambda value: value and value.strip() == 'FPTS Updated')
    clock = label.parent.parent.select_one('[data-role="localtime"][data-value]') if label else None
    if clock is None:
        raise ValueError('RotoGrinders update time unavailable')
    published = datetime.fromisoformat(clock['data-value'])
    if published.tzinfo is None or as_of.tzinfo is None:
        raise ValueError('RotoGrinders requires timezone-aware publication and review times')
    stamp = published.astimezone(ET)
    # Exact dated pre-tip schedule rows below identify the target slate.
    # A fresh previous-evening publication can cover that slate.
    if (slate != as_of.astimezone(ET).date()
            or stamp.date() not in {slate, slate - timedelta(days=1)}
            or not as_of - timedelta(hours=6) <= stamp <= as_of):
        raise ValueError('RotoGrinders estimates are stale or not for the current slate')
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
            projections.append(dict(common, points=round(sum(stats[key] * weight for key, weight in weights.items()), 2), paired_minutes=minutes))
    if not notes:
        raise ValueError('No verifiable public RotoGrinders estimates for upcoming games')
    return (notes, projections), f'{len(notes)} pre-tip estimates · updated {stamp:%I:%M %p ET}'


NBA_HOUSE = 'https://nbahouse.net/minutes'


def nba_house_minutes(slate, as_of):
    # Explicit date avoids the provider's default board lag around midnight.
    # Do not retrieve historical pages as fresh pre-lock evidence.
    if slate < as_of.astimezone(ET).date():
        raise ValueError('Historical NBA House minutes are not fresh pre-tip evidence')
    soup = BeautifulSoup(fetch(f'{NBA_HOUSE}/{slate.isoformat()}'), 'html.parser')
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
    # The relative Today heading alone can describe yesterday near midnight.
    # Require the provider's own dated filter to agree with the selected slate.
    date_labels = set(re.findall(r'\bToday\s*\((\d{1,2})/(\d{1,2})\)', soup.get_text(' ', strip=True)))
    if date_labels != {(str(slate.month), str(slate.day))}:
        raise ValueError('LineupExperts Today filter date does not match the contest')
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
    required = {'Player', 'Opp', 'FD Salary', 'Projection'}
    for table in soup.select('table'):
        headers = [col.get_text(' ', strip=True) for col in table.select('thead th')]
        if not required.issubset(headers):
            continue
        for row in table.select('tbody tr'):
            cells = [c.get_text(' ', strip=True) for c in row.find_all('td', recursive=False)]
            if len(cells) != len(headers):
                continue
            data = dict(zip(headers, cells))
            team, opponent = team_code(data.get('Team', '')), team_code(data['Opp'])
            try:
                salary = int(data['FD Salary'].replace('$', '').replace(',', ''))
                points = float(data['Projection'])
            except ValueError:
                continue
            if opponent and team != opponent and 0 < salary <= 60000 and 0 <= points <= 150:
                record = dict(player=data['Player'], reference_salary=salary, reference_points=points)
                if team:
                    record.update(team=team, game=f'{team}@{opponent}')
                elif 'Team' not in data:
                    # The public table may publish opponent but omit own team.
                    # Keep this explicitly reference-only; never invent the team.
                    record['reference_opponent'] = opponent
                else:
                    continue
                records.append(record)
    if not records:
        raise ValueError('FantasySportsEdge public projection table unavailable')
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


def match_opponent_reference(pool, records):
    """Reference-only matching when a board omits the player's own team.

    Require a unique contest name, exact salary and opponent on the contest
    game. Never transfer these records to the numerical consensus pipeline.
    """
    matches = []
    for record in records:
        key = player_key(record['player'])
        opponent = record['reference_opponent']
        ids = []
        for row in pool.itertuples():
            teams = row.game.split('@')
            if (len(teams) == 2 and len(set(teams)) == 2 and row.team in teams
                    and opponent in teams and opponent != row.team
                    and row.salary == record['reference_salary']
                    and key in contest_player_keys(row.fanduel_name, row.fanduel_id)):
                ids.append(row.fanduel_id)
        if len(ids) == 1:
            matches.append(dict(record, fanduel_id=ids[0]))
    return matches


def compare_reference(pool, records):
    exact = [row for row in records if 'reference_opponent' not in row]
    opponent_only = [row for row in records if 'reference_opponent' in row]
    matches = pd.DataFrame(match_public(pool, exact) + match_opponent_reference(pool, opponent_only))
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




def reference_review_queue(scored, boards, as_of):
    """Rank research gaps, never treat overlapping reference boards as consensus.

    Each row is one provider/player match. Unknown publication time is explicit.
    Old dated boards are excluded from the actionable queue. Scores are untouched.
    """
    columns = ['fanduel_id', 'Player', 'Salary', 'Provider', 'Published UTC',
               'DAILY FD', 'Model FD', 'Reference FD', 'FD gap',
               'Model minutes', 'Reference minutes', 'Minutes gap', 'Review']
    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        raise ValueError('Reference review requires a timezone-aware cutoff')
    if not scored.fanduel_id.is_unique:
        raise ValueError('Reference review requires unique contest IDs')
    rows = []
    for name in ('LineupExperts', 'FantasySportsEdge', 'Fantasy Team Advisors', 'MatchWiz', 'KeelStats'):
        if name not in boards:
            continue
        records, stamp = boards[name][:2]
        published = None if stamp is None else pd.Timestamp(stamp)
        if published is None:
            if name not in ('LineupExperts', 'MatchWiz'):
                continue
        elif (pd.isna(published) or published.tzinfo is None
              or not cutoff - pd.Timedelta(hours=6) <= published <= cutoff):
            continue
        if name == 'LineupExperts':
            matched = pd.DataFrame(match_public(scored, records))
            if matched.empty:
                continue
            compared = scored.loc[scored.eligible].merge(
                matched.drop_duplicates('fanduel_id', keep=False)[['fanduel_id', 'reference_fd']],
                on='fanduel_id', validate='one_to_one').rename(columns={'reference_fd':'reference_points'})
        elif name in ('MatchWiz', 'KeelStats'):
            if name == 'MatchWiz':
                # Retrieval timestamps are not publication timestamps.
                def recent(record):
                    try:
                        stamp = pd.Timestamp(record.get('retrieved_at'))
                        return (pd.notna(stamp) and stamp.tzinfo is not None
                                and cutoff - pd.Timedelta(hours=6) <= stamp <= cutoff
                                and record.get('slate_date') == cutoff.tz_convert(ET).date().isoformat())
                    except (ValueError, TypeError):
                        return False
                records = [record for record in records if recent(record)]
            compared = compare_keelstats(scored, records)
            if compared.empty:
                continue
            compared = compared.merge(scored[['fanduel_id','salary','projected_fd_points','adjusted_fd_points']],
                                      on='fanduel_id', validate='one_to_one')
        else:
            compared = compare_reference(scored, records)
        for row in compared.itertuples():
            def numeric(value, upper):
                value = pd.to_numeric(value, errors='coerce')
                return float(value) if pd.notna(value) and 0 <= value <= upper else None
            points = numeric(getattr(row, 'reference_points', None), 150)
            minutes = numeric(getattr(row, 'reference_minutes', None), 48)
            daily = numeric(row.projected_fd_points, 150)
            model = numeric(row.adjusted_fd_points, 150)
            model_minutes = numeric(row.adjusted_minutes, 48)
            gap = None if points is None or model is None else round(points-model, 2)
            minute_gap = None if minutes is None or model_minutes is None else round(minutes-model_minutes, 2)
            reasons = []
            if points is not None and points > 0 and (daily is None or daily <= 0):
                reasons.append('Missing DAILY points')
            if points is not None and points > 0 and (model is None or model <= 0):
                reasons.append('Missing usable model points')
            if gap is not None and abs(gap) >= 5:
                reasons.append('Points discrepancy')
            if minutes is not None and minutes > 0 and model_minutes is None:
                reasons.append('Missing model minutes')
            if minute_gap is not None and abs(minute_gap) >= 4:
                reasons.append('Minutes discrepancy')
            if not reasons:
                continue
            rows.append([row.fanduel_id, row.fanduel_name, row.salary, name,
                         'Unverified' if published is None else published.tz_convert('UTC').isoformat(),
                         daily, model, points, gap, model_minutes, minutes, minute_gap, '; '.join(reasons)])
    result = pd.DataFrame(rows, columns=columns)
    if result.empty:
        return result
    result['_missing'] = result.Review.str.contains('Missing')
    result['_gap'] = result[['FD gap', 'Minutes gap']].apply(pd.to_numeric, errors='coerce').abs().max(axis=1)
    return result.sort_values(['_missing', '_gap', 'fanduel_id', 'Provider'],
                              ascending=[False, False, True, True]).drop(columns=['_missing','_gap']).reset_index(drop=True)



KEELSTATS = 'https://keelstats.com/nba/usage'


def keelstats_reference(slate, as_of):
    """Dated minutes reference only; returning-player impact is not modeled."""
    soup = BeautifulSoup(fetch(KEELSTATS), 'html.parser')
    page = soup.get_text(' ', strip=True)
    if slate != as_of.astimezone(ET).date() or f'{slate:%A, %B} {slate.day}' not in page:
        raise ValueError('KeelStats slate date unavailable')
    stamp_match = re.search(r'Updated ([A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2} [AP]M) (E[DS]T)', page)
    if not stamp_match:
        raise ValueError('KeelStats update timestamp unavailable')
    stamp = datetime.strptime(stamp_match[1], '%b %d, %Y, %I:%M %p').replace(tzinfo=ET)
    if stamp.tzname() != stamp_match[2] or not as_of - timedelta(hours=6) <= stamp <= as_of:
        raise ValueError('KeelStats timestamp is stale or invalid')
    records = []
    for table in soup.select('table'):
        caption = table.find('caption')
        heading = table.find_previous('h3')
        game_heading = table.find_previous('h2')
        if not game_heading:
            continue
        match = re.fullmatch(r'(.+?) at (.+?)(?:\s*\d{1,2}:\d{2}\s*[AP]M)?', game_heading.get_text(' ', strip=True))
        if not match:
            continue
        away, home = map(team_code, match.groups())
        team = team_code(caption.get_text(' ', strip=True).split(':',1)[0]) if caption else ''
        if not team and heading:
            team = team_code(heading.get_text(' ', strip=True))
        if not away or not home or away == home or team not in (away, home):
            continue
        headers = [cell.get_text(' ', strip=True) for cell in table.select('thead th')]
        if not {'Player','L10','Tonight','USG%','GS'} <= set(headers) or len(set(headers)) != len(headers):
            continue
        for row in table.select('tbody tr'):
            cells = [cell.get_text(' ', strip=True) for cell in row.find_all(['td','th'], recursive=False)]
            if len(cells) != len(headers):
                continue
            fields = dict(zip(headers,cells))
            try:
                minutes = float(fields['Tonight'])
            except ValueError:
                continue
            if not fields['Player'] or not 0 <= minutes <= 48:
                continue
            records.append(dict(player=fields['Player'], team=team, game=f'{away}@{home}',
                                reference_minutes=minutes, reference_l10=fields['L10'],
                                reference_usage=fields['USG%'], reference_starts=fields['GS']))
    if not records:
        raise ValueError('KeelStats minutes table unavailable')
    return records, stamp


def compare_keelstats(scored, records):
    """Keep historical context and projected minutes separate from scoring inputs."""
    matches = pd.DataFrame(match_public(scored, records))
    if matches.empty:
        return matches
    compared = scored.loc[scored.eligible, ['fanduel_id','fanduel_name','adjusted_minutes']].merge(
        matches.drop_duplicates('fanduel_id',keep=False), on='fanduel_id', validate='one_to_one')
    compared['minutes_gap'] = (compared.reference_minutes - compared.adjusted_minutes).round(2)
    return compared.sort_values('minutes_gap',key=lambda col:col.abs(),ascending=False)


def get_reference_research(slate, as_of, contest_games):
    """Refresh public reference boards independently, without accepting scoring inputs."""
    from matchwiz_reference import matchwiz_reference
    if slate != as_of.astimezone(ET).date():
        return {}, {name: 'Historical slate: current reference not checked' for name in
                    ('LineupExperts', 'FantasySportsEdge', 'Fantasy Team Advisors', 'MatchWiz', 'KeelStats')}
    jobs = (
        ('LineupExperts', lambda: (lineupexperts_reference(slate, slate), None)),
        ('FantasySportsEdge', lambda: fantasysportsedge_reference(slate, as_of)),
        ('Fantasy Team Advisors', lambda: fta_nba_reference(slate, as_of, contest_games)),
        ('MatchWiz', lambda: (matchwiz_reference(slate, as_of), None)),
        ('KeelStats', lambda: keelstats_reference(slate, as_of)),
    )
    boards, status = {}, {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as workers:
        futures = [workers.submit(job) for _, job in jobs]
        for (name, _), future in zip(jobs, futures):
            try:
                result = future.result()
                if not result[0]:
                    status[name] = 'Reference checked: no public rows'
                    continue
                boards[name] = result
                status[name] = f'Reference checked: {len(result[0])} returned rows; not scoring evidence'
            except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
                status[name] = 'Reference unavailable for this slate or source format changed'
    return boards, status


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



def public_coverage(pool, notes, projections):
    """Measure actual contest matches, separately from accepted scoring evidence."""
    eligible = set(pool.loc[pool.eligible.eq(True), 'fanduel_id'])
    rows = []
    for kind, records, providers in (
        ('Points', projections, (DFF, PROPSIMS, ROTOGRINDERS)),
        ('Minutes', [row for row in notes if row.get('minutes') is not None],
         (RW_MINUTES, NBA_HOUSE, PROPSIMS, ROTOGRINDERS)),
    ):
        for source in providers:
            raw = [row for row in records if row.get('source') == source]
            matched = match_public(pool, raw)
            ids = {row['fanduel_id'] for row in matched}
            covered = ids & eligible
            rows.append({
                'Evidence': kind, 'Provider': source, 'Returned rows': len(raw),
                'Matched rows': len(matched), 'Unmatched rows': len(raw) - len(matched),
                'Eligible players matched': len(covered), 'Eligible players': len(eligible),
                'Eligible players missing': len(eligible) - len(covered),
            })
    return pd.DataFrame(rows)


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
        return pd.DataFrame(columns=['points', 'observed_at', 'source', 'source_count', 'spread', 'detail', 'inputs_json', 'propsims_distribution_json'])
    frame['family'] = frame.source.map(POINT_SOURCE_GROUPS)
    dated = frame.observed_at.astype('string').fillna('').str.strip()
    has_offset = dated.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$', regex=True)
    frame['time'] = pd.to_datetime(dated.where(has_offset), utc=True, errors='coerce', format='mixed')
    frame['points'] = pd.to_numeric(frame.points, errors='coerce')
    # Minutes are paired only when supplied alongside the same provider's points.
    frame['paired_minutes'] = pd.to_numeric(frame.get('paired_minutes', pd.Series(index=frame.index, dtype=float)), errors='coerce')
    frame['paired_minutes'] = frame.paired_minutes.where(frame.paired_minutes.gt(0) & frame.paired_minutes.le(60))
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
    # Relative recency weights are mathematically equivalent to absolute age weights.
    # Anchoring to each player's latest accepted estimate avoids clock-only score drift.
    relative_age = (frame.groupby('fanduel_id').time.transform('max') - frame.time).dt.total_seconds() / 3600
    frame['weight'] = 2 ** (-relative_age / 3)
    rows = {}
    for player, group in frame.groupby('fanduel_id'):
        distribution = []
        for item in group.loc[group.source.eq(PROPSIMS)].to_dict('records'):
            optional = {}
            for field, upper in (('fd_p10', 150), ('fd_p85', 150), ('play_probability', 1),
                                 ('conditional_fd_median', 150)):
                value = pd.to_numeric(item.get(field), errors='coerce')
                if pd.notna(value) and 0 <= value <= upper:
                    optional[field] = float(value)
            if not (optional.get('fd_p10', float('inf')) <= item['points']
                    <= optional.get('fd_p85', -1)):
                optional.pop('fd_p10', None)
                optional.pop('fd_p85', None)
            if optional:
                distribution.append(dict(source=PROPSIMS, observed_at=item['time'].isoformat(),
                                         fd_median=float(item['points']), **optional))
        rows[player] = dict(propsims_distribution_json=json.dumps(distribution), points=(group.points * group.weight).sum() / group.weight.sum(),
                            observed_at=group.time.max().isoformat(), source=', '.join(group.source),
                            source_count=len(group), spread=group.points.max() - group.points.min(),
                            detail=' · '.join(f'{row.family} {row.points:.2f}' for row in group.itertuples()),
                            inputs_json=group[['source', 'family', 'points', 'time', 'weight', 'paired_minutes']]
                                .rename(columns={'time': 'observed_at'})
                                .to_json(orient='records', date_format='iso', double_precision=15))
    return pd.DataFrame.from_dict(rows, orient='index', columns=['points', 'observed_at', 'source', 'source_count', 'spread', 'detail', 'inputs_json', 'propsims_distribution_json'])


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
        'propsims_distribution_json': 'propsims_distribution_json',
    }.items():
        result[target] = result.fanduel_id.map(independent[field])
    result['projection_source_count'] = result.projection_source_count.fillna(0).astype(int)
    result['projection_sources_json'] = result.projection_sources_json.fillna('[]')
    result['propsims_distribution_json'] = result.propsims_distribution_json.fillna('[]')
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
