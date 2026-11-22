"""Compare an archived contest pool with final NBA box scores."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from model import norm
from slate_import import game_code, matchup_key, player_key, team_code
from slate_research import ET, GAME_ID, NBA_WEB, games_for_date, nba_page, played_minutes

SCORE_WEIGHTS = {'points': 10, 'reboundsTotal': 12, 'assists': 15, 'steals': 30,
                 'blocks': 30, 'turnovers': -10}
VERIFIED_ABSENCES = {
    ('2026-11-18', 'CLE/MEM', 'CLE', 'rileyminix'):
        'https://www.nba.com/cavaliers/news/releases-zack-austin-261118',
}
# These source-name variants were confirmed in the saved November 18 identity audit.
BOX_NAME_ALIASES = {
    'michaelporterjr': 'michaelporter', 'treymurphyiii': 'treymurphy',
    'jabarismithjr': 'jabarismith', 'wendellcarterjr': 'wendellcarter',
    'jaimejaquezjr': 'jaimejaquez', 'kellyoubrejr': 'kellyoubre',
    'bobbyportisjr': 'bobbyportis', 'derecklivelyii': 'derecklively',
    'craigporterjr': 'craigporter', 'mikelbrownjr': 'mikelbrown',
    'walterclaytonjr': 'walterclayton', 'ronaldhollandii': 'ronhollandii',
    'morezjohnsonjr': 'morezjohnson', 'jaronpierrejr': 'jaronpierre',
    'garytrentjr': 'garytrent', 'larrynancejr': 'larrynance',
    'garypaytonii': 'garypayton', 'kevinmccullarjr': 'kevinmccullar',
    'labaronphilonjr': 'labaronphilon', 'scottypippenjr': 'scottypippen',
    'jimmybutleriii': 'jimmybutler', 'ernestudehjr': 'ernestudeh',
    'timhardawayjr': 'timhardaway',
}
SOURCE_ERRORS = (OSError, ValueError, TypeError, AttributeError, KeyError)


def result_name(name):
    return BOX_NAME_ALIASES.get(norm(name), player_key(name))


def game_matchup(game):
    return '@'.join(team_code(game[side]['teamTricode']) for side in ('awayTeam', 'homeTeam'))


def collect_final_boxes(day, matchups):
    """Use the dated league schedule and verify identity again on each final box."""
    candidates = defaultdict(list)
    for entry in games_for_date(day):
        matchup = matchup_key(game_code(game_matchup(entry)))
        if matchup in matchups:
            candidates[matchup].append(entry)

    def fetch_box(entry):
        game_id = str(entry['gameId'])
        if entry.get('gameStatus') != 3 or not GAME_ID.fullmatch(game_id):
            return None
        away, home = game_matchup(entry).lower().split('@')
        source = f'{NBA_WEB}/game/{away}-vs-{home}-{game_id}/box-score'
        try:
            game = nba_page(source)['game']
            stamp = pd.to_datetime(game['gameTimeUTC'], utc=True)
            if (game['gameId'] == game_id and game['gameStatus'] == 3
                    and stamp.tz_convert(ET).date() == day and game_matchup(game) == game_matchup(entry)):
                return game, source
        except SOURCE_ERRORS:
            return None
        return None

    unique = [entries[0] for entries in candidates.values() if len(entries) == 1]
    with ThreadPoolExecutor(max_workers=8) as workers:
        return [box for box in workers.map(fetch_box, unique) if box is not None]


def nba_outcomes(boxes):
    results = defaultdict(dict)
    verified_games = set()
    for game, source in boxes:
        matchup = matchup_key(game_matchup(game))
        verified_games.add(matchup)
        for side in ('awayTeam', 'homeTeam'):
            club = game[side]
            team = team_code(club['teamTricode'])
            players = [(row, False) for row in club.get('players', [])]
            players += [(row, True) for row in club.get('inactives', [])]
            for row, inactive in players:
                name = ' '.join(filter(None, (row.get('firstName'), row.get('familyName'))))
                person = row.get('personId')
                if not name or not person:
                    continue
                stats = row.get('statistics') or {}
                minutes = played_minutes(stats.get('minutes'))
                values = [stats.get(field) for field in SCORE_WEIGHTS]
                if minutes is not None and all(type(value) is int and value >= 0 for value in values):
                    points = sum(value * weight for value, weight in zip(values, SCORE_WEIGHTS.values())) / 10
                    outcome = ('Played', minutes, points, source)
                elif minutes is None and (inactive or 'DNP' in str(row.get('comment', '')).upper()):
                    outcome = ('Did not play', None, None, source)
                else:
                    outcome = ('Needs review', None, None, source)
                key = (matchup, team, result_name(name))
                existing = results[key].get(person)
                if existing is None or (existing[0] != 'Played' and outcome[0] != 'Needs review'):
                    results[key][person] = outcome
    return results, verified_games


def compare_results(pool, day, boxes, prior_scores):
    outcomes, finals = nba_outcomes(boxes)
    keys = [(matchup_key(game_code(row.game)), team_code(row.team), result_name(row.fanduel_name))
            for row in pool.itertuples()]
    counts = Counter(keys)
    comparisons = []
    for key in keys:
        candidates = outcomes.get(key, {})
        proof = VERIFIED_ABSENCES.get((day.isoformat(), *key))
        if counts[key] == 1 and len(candidates) == 1:
            outcome = next(iter(candidates.values()))
        elif counts[key] == 1 and not candidates and proof and key[0] in finals:
            outcome = ('Did not play', None, None, proof)
        else:
            status = 'Needs review' if key[0] in finals else 'Final box unavailable'
            outcome = (status, None, None, '')
        comparisons.append(outcome)
    columns = ['outcome', 'nba_actual_minutes', 'nba_fd_points', 'nba_source']
    result = pool[['fanduel_id', 'fanduel_name', 'team', 'game']].copy()
    for name in ('projected_fd_points', 'adjusted_fd_points', 'adjusted_minutes'):
        result[name] = pd.to_numeric(pool.get(name), errors='coerce')
    result[columns] = pd.DataFrame(comparisons, columns=columns, index=pool.index)
    for name in ('nba_actual_minutes', 'nba_fd_points'):
        result[name] = pd.to_numeric(result[name], errors='coerce')
    result['recorded_fd_points'] = pd.to_numeric(result.fanduel_id.map(prior_scores), errors='coerce')
    result['actual_comparison'] = ''
    both = result.nba_fd_points.notna() & result.recorded_fd_points.notna()
    difference = (result.nba_fd_points - result.recorded_fd_points).abs()
    result.loc[both & difference.le(.05), 'actual_comparison'] = 'Agrees'
    result.loc[both & difference.gt(.05), 'actual_comparison'] = 'Differs'
    result.loc[result.outcome.eq('Did not play') & result.recorded_fd_points.fillna(0).ne(0),
               'actual_comparison'] = 'Differs'
    result['fd_projection_error'] = (result.nba_fd_points - result.adjusted_fd_points).round(2)
    result['minutes_projection_error'] = (result.nba_actual_minutes - result.adjusted_minutes).round(2)
    return result, finals
