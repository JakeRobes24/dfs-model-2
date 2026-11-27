import csv
from io import StringIO

import pandas as pd
import pytest

from nfl_archived_lineups import compare_lineup_ranges, recover_lineups
from nfl_contest_import import NFL_SLOTS
from nfl_dst_results import FIELDS, final_dst_scores


def fixture():
    names = [f'Player {i}' for i in range(9)]
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['Id', 'Nickname', 'Position', 'Roster Position', 'Salary', 'Team', 'Game', 'Injury Indicator'])
    positions = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'RB', 'DEF']
    for i, (name, position) in enumerate(zip(names, positions)):
        club = ['KC', 'BUF', 'SF'][i % 3]
        eligibility = f'{position}/FLEX' if position in {'RB', 'WR', 'TE'} else position
        writer.writerow([f'136799-{i}', name, position, eligibility, 6000, club, f'ARI@{club}', ''])
    archive = dict(contest_id='136799', salary_cap=60000, all_player_salaries=dict.fromkeys(names, 6000),
                   lineups=[dict(label='Saved 1', players=names, salary_total=54000, projected_fd=110)])
    return csv_buffer.getvalue(), archive


def test_resolve_original_slots_and_salary_without_a_projection_file():
    raw, archive = fixture()
    pool, lineups = recover_lineups(raw, archive)
    assert len(pool) == 9
    assert [row['slot'] for row in lineups[0]['roster']] == list(NFL_SLOTS)
    assert lineups[0]['salary'] == 54000
    with pytest.raises(ValueError, match='slot, status or salary'):
        recover_lineups(raw.replace('ARI@KC,\r\n', 'ARI@KC,OUT\r\n'), archive)
    archive['lineups'][0]['players'][2] = archive['lineups'][0]['players'][1]
    with pytest.raises(ValueError, match='Classic roster constraints'):
        recover_lineups(raw, archive)


def test_dst_excludes_defensive_touchdown_from_points_allowed_and_rejects_ambiguity():
    key = dict(game_id='2026_11_ARI_KC', week=11, away_team='ARI', home_team='KC')
    schedule = pd.DataFrame([dict(key, season=2026, game_type='REG', gameday='2026-11-22',
                                  away_score=3, home_score=7)])
    base = dict.fromkeys(FIELDS)
    base.update(key, game_date='2026-11-22', season_type='REG')
    plays = pd.DataFrame([
        dict(base, play_id=1, play_type='pass', posteam='ARI', defteam='KC',
             touchdown=1, td_team='KC', return_touchdown=1, interception=1),
        dict(base, play_id=2, play_type='extra_point', posteam='KC', defteam='ARI', extra_point_result='good'),
        dict(base, play_id=3, play_type='field_goal', posteam='ARI', defteam='KC', field_goal_result='made'),
        dict(base, play_id=4, play_type='no_play', posteam='ARI', defteam='KC', sack=1),
    ])
    final, rejected = final_dst_scores(plays, schedule, season=2026)
    assert rejected == {}
    assert final.set_index('team')[['points_allowed', 'event_points', 'actual']].to_dict('index') == {
        'ARI': dict(points_allowed=1, event_points=0, actual=7),
        'KC': dict(points_allowed=3, event_points=8, actual=15),
    }
    assert list(final_dst_scores(plays.iloc[:-2], schedule, season=2026)[1].values()) == [
        'Scoring events do not match final score.']
    plays.loc[3, ['play_type', 'field_goal_result']] = ['field_goal', 'blocked']
    assert list(final_dst_scores(plays, schedule, season=2026)[1].values()) == [
        'Blocked kick requires settled scoring evidence.']


def test_stack_covariance_widens_roster_but_shared_players_cancel_from_pair():
    raw, archive = fixture()
    _, lineups = recover_lineups(raw, archive)
    first = lineups[0]
    replacement = dict(first['roster'][8], player_id='alternate')
    lineups.append(dict(first, label='Saved 2', roster=first['roster'][:8]+[replacement]))
    players = {
        row['player_id']: dict(position=row['positions'][0], team=row['team'], game=row['game'],
                               history_games=4, actual=15, baseline=10)
        for row in first['roster']
    }
    players['alternate'] = dict(players[first['roster'][8]['player_id']], baseline=9, actual=13)
    scales = dict.fromkeys(['QB', 'RB', 'WR', 'TE', 'DEF'], 4.)
    rows, pairs = compare_lineup_ranges(lineups, players, scales, {'WR': .25, 'TE': .23})
    assert rows[0]['historical_baseline'] == 90
    assert rows[0]['actual'] == 135
    assert rows[0]['ranges']['qb_pass_catcher']['width'] > rows[0]['ranges']['independent']['width']
    assert pairs[0]['left_actual_win'] == 1
    assert pairs[0]['shared_players'] == 8
    assert pairs[0]['policies']['qb_pass_catcher'] == pairs[0]['policies']['independent']
