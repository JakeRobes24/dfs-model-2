"""Public 4for4 weekly FanDuel reference, with exact contest reconciliation."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import re

from bs4 import BeautifulSoup

from nfl_daily_audit import ALIASES, game, norm, number, team
from nfl_projection_review import stamp

POSITIONS = ('QB', 'RB', 'WR', 'TE')
PAGES = 'https://www.4for4.com/fantasy-football-projections/fanduel'
FIELDS = {
    'ffpts': 'projection_fd', 'ruatt': 'rushing_attempts', 'ruydsrushing': 'rushing_yards',
    'rutd': 'rushing_td', 'rec': 'receptions', 'recydsreceiving': 'receiving_yards',
    'rectd': 'receiving_td', 'att': 'pass_attempts', 'payds': 'passing_yards',
    'patdpassing': 'passing_td', 'int': 'interceptions',
}
MAX_HTML = 2 * 1024 * 1024


def parse_4for4_page(html, *, season, week, position):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h1')
    expected = f'{season} Fantasy Football Projections - FanDuel - {position} - Week {week}'
    if title is None or title.get_text(' ', strip=True) != expected:
        raise ValueError('Wrong week, format or position.')
    times = {s.strip() for s in soup.find_all(string=lambda s: s and 'Projections as of ' in s)}
    if len(times) != 1:
        raise ValueError('Publication timestamp missing or conflicting.')
    match = re.fullmatch(r'Projections as of (.+) (EST|EDT)', times.pop())
    if not match:
        raise ValueError('Unrecognized publication timestamp.')
    published = datetime.strptime(match[1], '%A, %B %d, %Y at %I:%M %p').replace(
        tzinfo=ZoneInfo('America/New_York'))
    if published.tzname() != match[2]:
        raise ValueError('Conflicting publication timezone.')
    tables = soup.select('table.table_4for4')
    if len(tables) != 1:
        raise ValueError('Public projection table unavailable.')
    table = tables[0]
    columns = [norm(c.get_text(' ', strip=True)) for c in table.select('thead th')]
    if len(set(columns)) != len(columns) or not {'player', 'team', 'opp', 'ffpts'} <= set(columns):
        raise ValueError('Public projection table schema changed.')
    rows = []
    for row in table.select('tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) != len(columns):
            continue
        by_field = dict(zip(columns, cells))
        link = by_field['player'].select_one('a[href^="/player/"]')
        if link is None:
            continue
        values = {key: cell.get_text(' ', strip=True) for key, cell in by_field.items()}
        own = team(values['team'])
        opp_raw = values['opp']
        opp = team(opp_raw.removeprefix('@').strip())
        matchup = game(f'{opp}@{own}' if not opp_raw.startswith('@') else f'{own}@{opp}')
        components = {target: number(values.get(header)) for header, target in FIELDS.items()}
        points = components.pop('projection_fd')
        if not matchup or points is None or not -30 <= points <= 150:
            continue
        rows.append(dict(player=link.get_text(' ', strip=True), team=own, game=matchup,
                         position=position, projection_fd=points,
                         components={k: v for k, v in components.items() if v is not None and v >= 0},
                         provider_player=link['href']))
    return published, rows


def collect_4for4_reference(audit, *, season, week, cutoff_utc, now=None):
    """Collect the publicly visible rows at a known time. Never backdate observation."""
    if type(season) is not int or not 2000 <= season <= 2100 or type(week) is not int or not 1 <= week <= 18:
        raise ValueError('Use an NFL season and regular-season week.')
    cutoff = stamp(cutoff_utc)
    clock = now if now is not None else lambda: datetime.now(timezone.utc)

    def read(position):
        url = f'{PAGES}/{position.lower()}/{season}/week{week}'
        try:
            with urlopen(Request(url, headers={'User-Agent': 'DFSModelReference/2.0'}), timeout=8) as response:
                if response.geturl() != url:
                    raise ValueError('Unexpected reference page redirect.')
                page = response.read(MAX_HTML + 1)
            observed = clock()
            if len(page) > MAX_HTML:
                raise ValueError('Public page exceeds size limit.')
            published, rows = parse_4for4_page(page, season=season, week=week, position=position)
        except (OSError, ValueError):
            return position, url, None, None, [], 'Public page unavailable or invalid'
        if not published <= observed <= cutoff or cutoff - published > timedelta(hours=24):
            return position, url, published, observed, rows, 'Outside decision window'
        return position, url, published, observed, rows, 'Public reference read'

    keys = defaultdict(list)
    for player in audit['players']:
        player_id = player['player_id']
        name, club = norm(player['player']), team(player['team'])
        names = {name}
        alias = ALIASES.get(player_id.rsplit('-', 1)[-1])
        if alias and (name, club) == (alias[0], alias[2]):
            names.add(alias[1])
        for name_key in names:
            keys[name_key, club, game(player['game'])].append(player)

    coverage, matches = [], defaultdict(list)
    with ThreadPoolExecutor(max_workers=len(POSITIONS)) as pool:
        for position, url, published, observed, rows, status in pool.map(read, POSITIONS):
            matched = 0
            for row in rows if status == 'Public reference read' else ():
                hit = keys[norm(row['player']), row['team'], row['game']]
                if len(hit) == 1 and position in hit[0]['positions']:
                    player = hit[0]
                    if player['status'] in {'out', 'inactive', 'ir', 'suspended'}:
                        continue
                    matches[player['player_id']].append({
                        **row, 'source': url, 'published_at': published.isoformat(),
                        'observed_at': observed.isoformat(), 'player_id': player['player_id'],
                        'daily_fd': player['projection_fd'],
                    })
                    matched += 1
            coverage.append(dict(position=position, url=url, status=status, visible_rows=len(rows),
                                 matched_rows=matched, published_at=published.isoformat() if published else None,
                                 observed_at=observed.isoformat() if observed else None))
    return dict(contest_id=audit['contest_id'], cutoff_utc=cutoff_utc, season=season, week=week,
                contest_sha256=audit['contest_sha256'], daily_sha256=audit['daily_sha256'],
                coverage=coverage, rows=[v[0] for v in matches.values() if len(v) == 1],
                ambiguous_ids=sorted(k for k, v in matches.items() if len(v) != 1),
                purpose='Public weekly comparison. No consensus vote or projection replacement.')


PROPSIMS_FD = 'https://propsims.com/dfs/fanduel/'


def parse_propsims_fanduel(html, *, week, observed_at, games):
    """Return dated Sunday main-slate reference rows matched to scheduled games.

    Games map oriented matchups to timezone-aware kickoff strings. This
    captures a market-informed provider, without any scoring or contest claims.
    """
    cutoff = stamp(observed_at)
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    times = soup.select('time[datetime]')
    table = soup.select_one('table#dfstable')
    if (heading is None or heading.get_text(' ', strip=True) != f'FanDuel projections: Week {week} main slate'
            or len(times) != 1 or table is None):
        raise ValueError('Wrong week, scoring format, or source timestamp')
    published = stamp(times[0]['datetime'])
    if not published <= cutoff:
        raise ValueError('Future publication timestamp')
    columns = [c.get_text(' ', strip=True) for c in table.select('thead th')]
    if columns != ['Player', 'Salary', 'Median', 'Ceiling', 'Value']:
        raise ValueError('Unrecognized FanDuel reference columns')
    matches = defaultdict(list)
    for tr in table.select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != len(columns):
            continue
        name = cells[0].select_one('.pn')
        info = cells[0].select_one('.psub')
        if name is None or info is None:
            continue
        matchup = re.fullmatch(r'(QB|RB|WR|TE|K|DST|DEF) · ([A-Z]{2,3}) (vs|@) ([A-Z]{2,3})',
                               info.get_text(' ', strip=True))
        if not matchup:
            continue
        position, own, direction, opponent = matchup.groups()
        own, opponent = team(own), team(opponent)
        away_key, home_key = game(f'{own}@{opponent}'), game(f'{opponent}@{own}')
        # The board labels both sides “vs”. When no away marker is supplied,
        # require a unique scheduled match and take its official orientation.
        options = [key for key in (away_key, home_key) if key and key in games]
        if len(options) != 1 or (direction == '@' and options[0] != away_key):
            continue
        game_key = options[0]
        kickoff = games.get(game_key)
        if not kickoff or not cutoff < stamp(kickoff):
            continue
        kickoff_stamp = stamp(kickoff).astimezone(ZoneInfo('America/New_York'))
        if kickoff_stamp.weekday() != 6 or not 13 <= kickoff_stamp.hour < 19:
            continue
        player = name.get_text(' ', strip=True)
        link = name.select_one('a[href^="/players/"]')
        provider_id = link['href'] if link is not None else None
        median, ceiling = (number(cell.get_text(strip=True)) for cell in cells[2:4])
        if not norm(player) or median is None or ceiling is None or not -10 <= median <= ceiling <= 120:
            continue
        matches[norm(player), own, game_key].append(dict(
            player=player, team=own, game=game_key, position=position, provider_player=provider_id,
            median_fd=median, p85_fd=ceiling, published_at=published.isoformat(),
            observed_at=cutoff.isoformat(), kickoff=kickoff_stamp.isoformat(), source=PROPSIMS_FD))
    return [rows[0] for rows in matches.values() if len(rows) == 1]
