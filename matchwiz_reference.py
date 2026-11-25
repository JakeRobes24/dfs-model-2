"""MatchWiz public lineup reference. Never contributes to scoring consensus."""
import re
import json
from collections import Counter
import pandas as pd
from bs4 import BeautifulSoup
from slate_import import game_code, team_code
from slate_research import ET, fetch, match_public

MATCHWIZ = 'https://matchwiz.ai/nba/lineups'


def parse_matchwiz(raw, slate, as_of):
    """Require explicit target date, exact matchup and both identified clubs.

    Retrieval time is not publication time. Projected roles and partial stats
    must not be promoted to official confirmations or complete FD forecasts.
    """
    if as_of.tzinfo is None or slate != as_of.astimezone(ET).date():
        raise ValueError('MatchWiz requires current slate and timezone-aware retrieval')
    soup = BeautifulSoup(raw, 'html.parser')
    subtitle = soup.select_one('p.subtitle')
    date_label = f'{slate:%A, %B} {slate.day}, {slate.year}'
    if subtitle is None or date_label not in subtitle.get_text(' ', strip=True):
        raise ValueError('MatchWiz slate date unavailable')
    records = []
    for game in soup.select('article.nbalu-game'):
        label = game.select_one('.nbalu-matchup')
        if label is None:
            continue
        matchup = game_code(label.get_text(' ', strip=True))
        if not matchup:
            continue
        sides = game.select('section.nbalu-side')
        clubs = []
        for side in sides:
            logo = side.select_one('.nbalu-club img[alt]')
            clubs.append(team_code(logo['alt'].removesuffix(' logo')) if logo else '')
        if len(sides) != 2 or set(clubs) != set(matchup.split('@')):
            continue
        for side, team in zip(sides, clubs):
            for table in side.select('.nbalu-table'):
                header = table.select_one('.nbalu-head')
                if header is None:
                    continue
                headers = [x.get_text(' ', strip=True) for x in header.find_all('span', recursive=False)]
                if headers[1:5] != ['Min','Pts','Reb','Ast']:
                    continue
                for row in table.select('li.nbalu-row[data-name][data-pid]'):
                    minutes = row.select_one('.nbalu-min')
                    link = row.select_one('.nbalu-name a')
                    name = row['data-name'].strip()
                    if not name or link is None or link.get_text(' ', strip=True) != name or minutes is None:
                        continue
                    try:
                        value = float(minutes.get_text(strip=True))
                    except ValueError:
                        continue
                    if not 0 <= value <= 48 or not re.fullmatch(r'\d+', row['data-pid']):
                        continue
                    record = dict(player=name, team=team, game=matchup, reference_minutes=value,
                                  provider_player_id=row['data-pid'],
                                  reference_role='starter listing' if 'nbalu-starter' in row.get('class', []) else 'nonstarter listing',
                                  retrieved_at=as_of.isoformat(), slate_date=slate.isoformat(), source=MATCHWIZ)
                    stats = row.select('.nbalu-stat .nbalu-statv')
                    for field, cell, maximum in zip(('reference_pts','reference_reb','reference_ast'), stats, (100,60,50)):
                        try:
                            number = float(cell.get_text(strip=True))
                        except ValueError:
                            continue
                        if 0 <= number <= maximum:
                            record[field] = number
                    records.append(record)
    if not records:
        raise ValueError('MatchWiz minutes rows unavailable')
    return records


def matchwiz_reference(slate, as_of):
    return parse_matchwiz(fetch(MATCHWIZ), slate, as_of)


def freeze_matchwiz_reference(pool, rows, slate, as_of):
    """Preserve eligible exact matches, separately from accepted scoring evidence."""
    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None or cutoff.tz_convert(ET).date() != slate:
        raise ValueError('Reference archive requires current slate and aware capture time.')
    if pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique:
        raise ValueError('Reference archive requires distinct player IDs.')
    valid = []
    ids = Counter(row.get('provider_player_id') for row in rows)
    for row in rows:
        if row.get('source') != MATCHWIZ or row.get('slate_date') != slate.isoformat():
            continue
        try:
            stamp = pd.Timestamp(row['retrieved_at'])
            minutes = float(row['reference_minutes'])
        except (TypeError, ValueError, KeyError):
            continue
        if (pd.isna(stamp) or stamp.tzinfo is None or not cutoff-pd.Timedelta(hours=6) <= stamp <= cutoff
                or not 0 <= minutes <= 48 or ids[row.get('provider_player_id')] != 1
                or not re.fullmatch(r'[0-9]+', str(row.get('provider_player_id','')))):
            continue
        valid.append(dict(row, reference_minutes=minutes, publication_time_verified=False))
    matches = match_public(pool, valid)
    counts = Counter(row['fanduel_id'] for row in matches)
    eligible = set(pool.loc[pool.eligible.eq(True),'fanduel_id'])
    evidence = {row['fanduel_id']: json.dumps(row, allow_nan=False)
                for row in matches if row['fanduel_id'] in eligible and counts[row['fanduel_id']] == 1}
    return pool.assign(matchwiz_reference_json=pool.fanduel_id.map(evidence).fillna(''))
