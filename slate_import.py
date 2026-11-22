"""Read the original FanDuel and DAILY exports without changing contest authority."""
import csv
from io import StringIO
import re

import numpy as np
import pandas as pd

from model import SLOTS, allowed_slots, norm
from pool_coverage import VERIFIED_ALIASES


TEAM_ALIASES = {
    'bkn': 'BKN', 'brk': 'BKN', 'bro': 'BKN', 'gs': 'GSW', 'no': 'NOP',
    'ny': 'NYK', 'sa': 'SAS', 'utah': 'UTA', 'wsh': 'WAS', 'pho': 'PHX',
}
NBA_TEAMS = (
    'ATL:Atlanta Hawks;BOS:Boston Celtics;BKN:Brooklyn Nets;CHA:Charlotte Hornets;'
    'CHI:Chicago Bulls;CLE:Cleveland Cavaliers;DAL:Dallas Mavericks;DEN:Denver Nuggets;'
    'DET:Detroit Pistons;GSW:Golden State Warriors;HOU:Houston Rockets;IND:Indiana Pacers;'
    'LAC:LA Clippers;LAL:Los Angeles Lakers;MEM:Memphis Grizzlies;MIA:Miami Heat;'
    'MIL:Milwaukee Bucks;MIN:Minnesota Timberwolves;NOP:New Orleans Pelicans;NYK:New York Knicks;'
    'OKC:Oklahoma City Thunder;ORL:Orlando Magic;PHI:Philadelphia 76ers;PHX:Phoenix Suns;'
    'POR:Portland Trail Blazers;SAC:Sacramento Kings;SAS:San Antonio Spurs;TOR:Toronto Raptors;'
    'UTA:Utah Jazz;WAS:Washington Wizards'
)
TEAM_CODES = {norm(name): code for code, name in (item.split(':') for item in NBA_TEAMS.split(';'))}
TEAM_CODES.update({'losangelesclippers': 'LAC', **TEAM_ALIASES})
VALID_TEAMS = set(TEAM_CODES.values())


def team_code(value):
    key = norm(value)
    return TEAM_CODES.get(key, key.upper() if key.upper() in VALID_TEAMS else '')


def game_code(value):
    teams = [team_code(team) for team in re.split(r'\s*(?:@|\bvs\.?\s+)\s*', str(value), flags=re.I)]
    return '@'.join(teams) if len(teams) == 2 and all(teams) and teams[0] != teams[1] else ''


def read_export(raw, header_fields):
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Each slate CSV must be smaller than 8 MiB.')
    lines = raw.decode('utf-8-sig').splitlines(keepends=True)
    for index, line in enumerate(lines[:40]):
        if header_fields <= {norm(col) for col in next(csv.reader([line]))}:
            return pd.read_csv(StringIO(''.join(lines[index:])), dtype=str, keep_default_na=False)
    raise ValueError('The CSV header was not recognized. Use the original player-list or DAILY export.')


def field(frame, *names, required=True):
    headers = {norm(col): col for col in frame}
    for name in names:
        if norm(name) in headers:
            return frame[headers[norm(name)]].str.strip()
    if required:
        raise ValueError('CSV is missing the ' + names[0] + ' column.')
    return pd.Series('', index=frame.index)


def number(series):
    return pd.to_numeric(series.str.replace(r'[$,]', '', regex=True), errors='coerce').replace(
        [np.inf, -np.inf], np.nan,
    )


def player_key(value):
    key = norm(value)
    return VERIFIED_ALIASES.get(key, key)


# These shortened FanDuel names were verified against the original Nov. 22
# contest and DAILY exports. Require both the player suffix and the short name.
VERIFIED_SUFFIX_ALIASES = {
    '84676': ('wendellcarter', 'wendellcarterjr'),
    '228120': ('walterclayton', 'walterclaytonjr'),
    '248942': ('morezjohnson', 'morezjohnsonjr'),
    '84679': ('marvinbagley', 'marvinbagleyiii'),
    '58519': ('garypayton', 'garypaytonii'),
    '20992': ('larrynance', 'larrynancejr'),
    '248943': ('chriscenac', 'chriscenacjr'),
    '171660': ('ronharper', 'ronharperjr'),
    '84683': ('jarenjackson', 'jarenjacksonjr'),
    '203732': ('daronholmes', 'daronholmesii'),
    '15846': ('timhardaway', 'timhardawayjr'),
}


def contest_player_key(name, fanduel_id):
    key = player_key(name)
    alias = VERIFIED_SUFFIX_ALIASES.get(fanduel_id.rsplit('-', 1)[-1])
    return alias[1] if alias and key == alias[0] else key


def matchup_key(game):
    return '/'.join(sorted(game.split('@'))) if game else ''


def reconcile_exports(contest_raw, daily_raw):
    contest = read_export(contest_raw, {'id', 'salary', 'game'})
    daily = read_export(daily_raw, {'player', 'minutes', 'fantasy'})
    # Some FanDuel templates carry entry fields to the left of the player list.
    id_columns = [col for col in contest if re.fullmatch(r'id(?:\.\d+)?', col.strip(), re.I)]
    player_id_columns = [col for col in id_columns if contest[col].str.fullmatch(r'\d+-\d+').any()]
    if len(player_id_columns) != 1:
        raise ValueError('Could not identify one FanDuel player ID column.')
    ids = contest[player_id_columns[0]].str.strip()
    valid_rows = ids.ne('') | field(contest, 'Salary').ne('')
    contest, ids = contest.loc[valid_rows], ids.loc[valid_rows]
    if ids.empty or not ids.str.fullmatch(r'\d+-\d+').all() or ids.duplicated().any():
        raise ValueError('Expected distinct FanDuel player IDs in the format contest-player.')
    contest_ids = ids.str.split('-').str[0].unique()
    if len(contest_ids) != 1:
        raise ValueError('This file mixes FanDuel contest IDs. Load one contest at a time.')

    display = field(contest, 'Nickname', 'Player Name', required=False)
    full_name = (field(contest, 'First Name', required=False) + ' '
                 + field(contest, 'Last Name', required=False)).str.strip()
    pool = pd.DataFrame({
        'fanduel_id': ids, 'fanduel_name': display.where(display.ne(''), full_name),
        'game': field(contest, 'Game').map(game_code),
        'team': field(contest, 'Team').map(team_code),
        'salary': number(field(contest, 'Salary')),
        'position': field(contest, 'Position'),
        'roster_eligibility': field(contest, 'Roster Position', 'Roster Eligibility').str.upper(),
        'injury_flag': field(contest, 'Injury Indicator', 'Injury Flag', required=False).str.upper().replace('OUT', 'O'),
    }).reset_index(drop=True)
    valid_slots = set(SLOTS)
    if (pool.fanduel_name.eq('').any() or pool.position.eq('').any() or not pool.salary.between(1, 60000).all()
            or pool.salary.mod(1).ne(0).any() or pool.game.eq('').any()
            or not all(team in game.split('@') for team, game in zip(pool.team, pool.game))
            or not pool.roster_eligibility.map(lambda value: bool(allowed_slots(value)) and
                                              allowed_slots(value) <= valid_slots).all()
            or set().union(*pool.roster_eligibility.map(allowed_slots)) != valid_slots):
        raise ValueError('Contest rows must have valid NBA teams, games, salary, names and complete FanDuel NBA classic roster eligibility.')
    pool['salary'] = pool.salary.astype(int)
    matchups = pool.game.map(matchup_key)
    original_keys = list(zip(pool.fanduel_name.map(player_key), pool.team, matchups))
    canonical = [contest_player_key(name, pid) for name, pid in zip(pool.fanduel_name, pool.fanduel_id)]
    pool['daily_key'] = list(zip(canonical, pool.team, matchups))
    scoped_aliases = {old: new for old, new in zip(original_keys, pool.daily_key) if old != new}
    # A second contest player with the same short key makes the mapping ambiguous.
    pool['daily_key'] = pool.daily_key.map(lambda key: scoped_aliases.get(key, key))
    daily['daily_name'] = field(daily, 'Player')
    daily['daily_key'] = list(zip(daily.daily_name.map(player_key), field(daily, 'Team').map(team_code),
                                 field(daily, 'GameInfo', 'Game').map(game_code).map(matchup_key)))
    daily['daily_key'] = daily.daily_key.map(lambda key: scoped_aliases.get(key, key))
    daily['projected_minutes'] = number(field(daily, 'Minutes')).where(lambda x: x.gt(0) & x.le(48))
    daily['projected_fd_points'] = number(field(daily, 'Fantasy'))
    daily['daily_salary'] = number(field(daily, 'Salary', required=False))
    daily['duplicate_daily'] = daily.daily_key.duplicated(keep=False) | daily.daily_key.isin(
        set(pool.loc[pool.daily_key.duplicated(keep=False), 'daily_key'])
    )
    duplicate_keys = set(daily.loc[daily.duplicate_daily, 'daily_key'])
    matched = pool.merge(
        daily.loc[~daily.duplicate_daily, ['daily_key', 'daily_name', 'projected_minutes',
                                          'projected_fd_points', 'daily_salary']],
        on='daily_key', how='left', validate='many_to_one',
    )
    unmatched = matched.daily_name.isna()
    matched['identity_match'] = np.select(
        [matched.daily_key.isin(duplicate_keys), unmatched,
         matched.fanduel_name.map(norm).ne(matched.daily_name.map(norm))],
        ['ambiguous', 'unmatched', 'known_alias'], default='exact',
    )
    matched['import_issue'] = np.select([
        matched.daily_key.isin(duplicate_keys), unmatched,
        matched.projected_minutes.isna() | matched.projected_fd_points.isna(),
        matched.daily_salary.notna() & matched.daily_salary.ne(matched.salary),
    ], ['Ambiguous identity', 'No verified DAILY name/team/game match', 'Missing or invalid DAILY minutes/points',
        'DAILY salary differs. FanDuel salary used.'], default='')
    extra_rows = int((~daily.daily_key.isin(set(pool.daily_key))).sum())
    return matched.drop(columns='daily_key'), str(contest_ids[0]), extra_rows
