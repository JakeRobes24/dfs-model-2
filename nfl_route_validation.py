"""Read public NFL route recaps and test historical receiving workload forecasts."""
from collections import Counter, defaultdict
from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup

from nfl_daily_audit import norm, team
from nfl_expected_opportunity_validation import matched_opportunity

OFFENSE = ('RB', 'WR', 'TE')
EASTERN = ZoneInfo('America/New_York')
HEADERS = ['', '', 'Snaps', 'Routes', 'RushLine', 'Receiving', 'Tgts', 'AY',
           'Sn%', 'Rt%', 'Tg%', 'AY%', 'TPRR']
EARLY_HEADERS = ['', '', 'Snaps', 'Routes', 'Rushing', 'Receiving', 'Tgts',
                 'TgtSh', 'TPRR', 'aDOT', 'AY', 'AY Sh']


def _count(value):
    match = re.fullmatch(r'([0-9]+)(?:\s+\([0-9]+%\))?', value)
    return int(match[1]) if match else None


def _article_updated(soup, *, season, week):
    title = soup.find('h1')
    if not title or title.get_text(' ', strip=True) != f'NFL Box Score Breakdown: Week {week} Recap & Usage Stats':
        raise ValueError('Unexpected NFL weekly recap title.')
    timestamps = []
    for element in soup.select('script[type="application/ld+json"]'):
        payload = json.loads(element.get_text())
        if isinstance(payload, dict) and payload.get('datePublished') and payload.get('dateModified'):
            published = datetime.fromisoformat(payload['datePublished'])
            modified = datetime.fromisoformat(payload['dateModified'])
            if published.tzinfo is None or modified.tzinfo is None or modified < published:
                raise ValueError('Invalid NFL recap publication dates.')
            timestamps.append(modified)
    if len(set(timestamps)) != 1 or timestamps[0].astimezone(EASTERN).year != season:
        raise ValueError('A verified recap modification time is required.')
    return timestamps[0].isoformat()


def parse_route_recap(raw, *, season, week):
    """Keep exact recap matchup, recorded scoring, raw routes and source timing."""
    soup = BeautifulSoup(raw, 'html.parser')
    updated = _article_updated(soup, season=season, week=week)
    matchup, club, dropbacks = None, None, None
    candidates = defaultdict(list)
    for node in soup.find_all(['h2', 'p', 'table']):
        if node.name == 'h2':
            heading = node.get_text(' ', strip=True)
            clubs = [team(icon.get('alt', '')) for icon in node.find_all('img')]
            scores = tuple(map(int, re.findall(r'\(([0-9]+)\)', heading)))
            if len(clubs) == 2:
                matchup = (clubs, scores) if all(clubs) and len(scores) == 2 else None
                club, dropbacks = None, None
            elif ' Personnel:' in heading:
                club = clubs[0] if len(clubs) == 1 else None
                dropbacks = None
        elif node.name == 'p' and club:
            match = re.search(r'/\s*([0-9]+)\s+Dropbacks?\b', node.get_text(' ', strip=True), re.I)
            if match:
                dropbacks = int(match[1])
        elif node.name == 'table' and matchup and club in matchup[0] and dropbacks:
            headers = [cell.get_text(' ', strip=True) for cell in node.select('thead th')]
            if headers not in (HEADERS, EARLY_HEADERS):
                continue
            for tr in node.select('tbody tr'):
                cells = tr.find_all('td', recursive=False)
                if len(cells) != len(headers):
                    continue
                position, _, snap_cell, route_cell, _, receiving, targets, *_ = [c.get_text(' ', strip=True) for c in cells]
                link = cells[1].find('a', href=True)
                if position not in OFFENSE or not link:
                    continue
                name = norm(link.get_text(' ', strip=True))
                snaps, routes = _count(snap_cell), _count(route_cell)
                if not name or snaps is None or routes is None or not 0 <= routes <= min(snaps, dropbacks):
                    continue
                box = re.fullmatch(r'([0-9]+)-(-?[0-9]+)-([0-9]+)', receiving)
                target_count = _count(targets)
                if (targets and target_count is None) or (receiving and box is None):
                    continue
                if target_count is not None and target_count > routes:
                    continue
                away, home = matchup[0]
                row = dict(week=week, away=away, home=home, away_score=matchup[1][0], home_score=matchup[1][1],
                           club=club, name=name, position=position, routes=routes, dropbacks=dropbacks,
                           source_targets=target_count, source_receiving_yards=int(box[2]) if box else None,
                           source_updated=updated)
                candidates[(away, home, club, name)].append(row)
    return [rows[0] for rows in candidates.values() if all(row == rows[0] for row in rows)]


def reconcile_routes(parsed, schedule, workload, *, season):
    """Require final matchup score, uniquely matched player and known box-count agreement."""
    games = schedule.loc[schedule.season.eq(season) & schedule.game_type.eq('REG')].copy()
    games['away'] = games.away_team.map(team)
    games['home'] = games.home_team.map(team)
    games = games.dropna(subset=['away_score', 'home_score', 'gametime'])
    games = games.drop_duplicates(['week', 'away', 'home'], keep=False)
    by_game = {(row.week, row.away, row.home): row for row in games.itertuples(index=False)}
    index = defaultdict(list)
    for row in workload.itertuples(index=False):
        index[row.game_id, team(row.team), norm(row.player), row.position].append(row)
    matched, reasons = [], Counter()
    for row in parsed:
        game = by_game.get((row['week'], row['away'], row['home']))
        if game is None or (game.away_score, game.home_score) != (row['away_score'], row['home_score']):
            reasons['Unverified matchup or final score'] += 1
            continue
        kickoff = datetime.fromisoformat(f'{game.gameday}T{game.gametime}').replace(tzinfo=EASTERN)
        if not kickoff < datetime.fromisoformat(row['source_updated']):
            reasons['Recap timestamp does not follow kickoff'] += 1
            continue
        hits = index[game.game_id, row['club'], row['name'], row['position']]
        if len(hits) != 1:
            reasons['Unverified player identity'] += 1
            continue
        hit, = hits
        if ((row['source_targets'] or 0) != hit.targets
                or (row['source_receiving_yards'] or 0) != hit.receiving_yards
                or row['routes'] > hit.offense_snaps):
            reasons['Counting stats or snap bound disagree'] += 1
            continue
        matched.append(dict(hit._asdict(), routes=row['routes'], dropbacks=row['dropbacks'],
                            kickoff=kickoff.isoformat(), source_updated=row['source_updated']))
    if not matched:
        return pd.DataFrame(), dict(reasons)
    exact = pd.DataFrame(matched)
    ambiguous = exact.duplicated(['game_id', 'gsis_id', 'team'], keep=False)
    if ambiguous.any():
        reasons['Duplicate verified player-game'] += int(ambiguous.sum())
    return exact.loc[~ambiguous].reset_index(drop=True), dict(reasons)


def compare_route_forecasts(rows, weekly, *, season):
    """Use only four earlier published recaps. Evaluate targets and receiving FD."""
    if rows.empty:
        return pd.DataFrame()
    rows = matched_opportunity(rows, weekly, season=season, channel='receiving')
    forecast_rows = []
    for _, history in rows.groupby(['gsis_id', 'team']):
        records = history.sort_values('team_game_number').to_dict('records')
        for i in range(4, len(records)):
            prior, target = records[i-4:i], records[i]
            seq = target['team_game_number']
            if [row['team_game_number'] for row in prior] != list(range(seq-4, seq)):
                continue
            kickoff = datetime.fromisoformat(target['kickoff'])
            if any(datetime.fromisoformat(row['source_updated']) >= kickoff
                   or datetime.fromisoformat(row['kickoff']) >= kickoff
                   or row['position'] != target['position'] for row in prior):
                continue
            routes = sum(row['routes'] for row in prior)
            targets = sum(row['targets'] for row in prior)
            if routes < 20 or targets < 4 or not all(pd.notna(row['expected_fd']) for row in [*prior, target]):
                continue
            dropbacks = sum(row['dropbacks'] for row in prior)
            recent_routes = sum(row['routes'] for row in prior[-2:])
            recent_dropbacks = sum(row['dropbacks'] for row in prior[-2:])
            target_rate = targets/routes
            baseline_targets = targets/4
            route_targets = dropbacks/4*recent_routes/recent_dropbacks*target_rate
            equal_targets = (baseline_targets+route_targets)/2
            baseline_fd = sum(row['actual_fd'] for row in prior)/4
            expected_fd = sum(row['expected_fd'] for row in prior)/4
            rates = [
                ('Four-game actual', baseline_targets, baseline_fd),
                ('Four-game expected', baseline_targets, expected_fd),
                ('Recent route share and expected', route_targets, route_targets*expected_fd/baseline_targets),
                ('Equal route blend and expected', equal_targets, equal_targets*expected_fd/baseline_targets),
            ]
            for policy, forecast, fd in rates:
                forecast_rows.append(dict(game_id=target['game_id'], week=target['week'], team=target['team'],
                                          gsis_id=target['gsis_id'], position=target['position'], policy=policy,
                                          actual_targets=target['targets'], targets=forecast,
                                          targets_error=abs(forecast-target['targets']), actual_fd=target['actual_fd'],
                                          fd=fd, fd_error=abs(fd-target['actual_fd'])))
    return pd.DataFrame(forecast_rows)
