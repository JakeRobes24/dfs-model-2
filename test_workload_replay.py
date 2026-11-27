from datetime import date

import pandas as pd
import pytest

from nba_shooting_workload import box_shooting_rows, compare_shooting_workload
from nfl_route_validation import (EARLY_HEADERS, HEADERS, compare_route_forecasts,
                                  parse_route_recap, reconcile_routes)


def test_box_score_reconciles_shot_types_and_final_points():
    stats = dict(minutes='30:00', points=24, fieldGoalsMade=9, fieldGoalsAttempted=18,
                 threePointersMade=3, threePointersAttempted=8, freeThrowsMade=3,
                 freeThrowsAttempted=4, reboundsTotal=4, assists=4, steals=1, blocks=0, turnovers=2)
    box = dict(gameId='123', awayTeam=dict(teamTricode='BOS', players=[
        dict(personId=55, statistics=stats)]), homeTeam=dict(teamTricode='NYK', players=[]))
    game = ('2026-11-01', '123', 'BOS', 'NYK')
    row, = box_shooting_rows(game, {'boxScoreTraditional': box})
    assert (row['twos_made'], row['twos_attempted'], row['points']) == (6, 10, 24)
    assert row['non_points_fd'] == pytest.approx(11.8)
    stats['points'] = 25
    assert not box_shooting_rows(game, {'boxScoreTraditional': box})
    with pytest.raises(ValueError, match='scheduled team'):
        box_shooting_rows(('2026-11-01', '123', 'NYK', 'BOS'), {'boxScoreTraditional': box})


def test_shot_mix_comparison_has_common_support_and_uses_strictly_earlier_data():
    schedule = [(date(2026, 11, i).isoformat(), str(i), 'BOS', 'NYK') for i in range(1, 10)]
    history = pd.DataFrame([dict(date=day, game_id=gid, team='BOS', nba_id='55', minutes=30,
                                 twos_made=5, twos_attempted=10, threes_made=2, threes_attempted=5,
                                 free_throws_made=2, free_throws_attempted=3, points=18, non_points_fd=10)
                            for day, gid, *_ in schedule])
    first = compare_shooting_workload(history, schedule)
    assert len(first) == 8 and first.game_id.eq('9').all()
    assert first.forecast_fd.tolist() == pytest.approx([28]*8)
    changes = history.assign(points=history.points.where(history.game_id.ne('9'), 45),
                             twos_made=history.twos_made.where(history.game_id.ne('9'), 30))
    assert compare_shooting_workload(changes, schedule).forecast_fd.tolist() == pytest.approx([28]*8)
    assert compare_shooting_workload(history.drop(2), schedule).empty


@pytest.mark.parametrize('columns', [HEADERS, EARLY_HEADERS])
def test_route_recap_binds_team_player_score_and_box_counts(columns):
    headers = ''.join(f'<th>{header}</th>' for header in columns)
    values = ('WR', '<a href="/player/receiver">Test Receiver</a>*', '50 (80%)', '32 (80%)',
              '', '5-35-0', '6 (23%)', '', '', '', '', '', '')
    cells = ''.join(f'<td>{cell}</td>' for cell in values[:len(columns)])
    html = f'''
    <h1>NFL Box Score Breakdown: Week 7 Recap &amp; Usage Stats</h1>
    <script type="application/ld+json">
    {{"datePublished": "2026-10-26T12:00-04:00", "dateModified": "2026-10-27T12:00-04:00"}}
    </script>
    <h2><img alt="BUF"/>Bills (20) at <img alt="MIA"/>Dolphins (17)</h2>
    <h2><img alt="BUF"/>Bills Personnel: 11p</h2>
    <p>51 Plays / 40 Dropbacks (78%)</p>
    <table><thead><tr>{headers}</tr></thead><tbody><tr>{cells}</tr></tbody></table>
    '''
    parsed = parse_route_recap(html, season=2026, week=7)
    assert len(parsed) == 1 and parsed[0]['routes'] == 32
    schedule = pd.DataFrame([dict(season=2026, week=7, game_type='REG', away_team='BUF', home_team='MIA',
                                  game_id='2026_07_BUF_MIA', away_score=20, home_score=17,
                                  gameday='2026-10-25', gametime='13:00')])
    workload = pd.DataFrame([dict(game_id='2026_07_BUF_MIA', gsis_id='123', team='BUF',
                                  player='Test Receiver', position='WR', targets=6,
                                  receiving_yards=35, offense_snaps=50)])
    result, reasons = reconcile_routes(parsed, schedule, workload, season=2026)
    assert result.routes.tolist() == [32] and not reasons
    assert reconcile_routes(parsed, schedule, workload.assign(targets=5), season=2026)[0].empty
    assert reconcile_routes(parsed, schedule.assign(home_score=21), workload, season=2026)[0].empty


def test_route_replay_excludes_recaps_updated_after_target_kickoff():
    rows = []
    scoring = []
    for i in range(1, 6):
        rows.append(dict(game_id=str(i), gsis_id='a', team='BUF', week=i, team_game_number=i,
                         position='WR', targets=6, routes=30, dropbacks=42, receiving_yards=50,
                         kickoff=f'2026-10-{i:02}T12:00-04:00', source_updated=f'2026-10-{i:02}T22:00-04:00'))
        scoring.append(dict(game_id=str(i), player_id='a', posteam='BUF', week=i, season=2026,
                            position='WR', rec_attempt=6, receptions=4, rec_yards_gained=50,
                            rec_touchdown=0, rec_two_point_conv=0, receptions_exp=4,
                            rec_yards_gained_exp=70, rec_touchdown_exp=0, rec_two_point_conv_exp=0))
    frame, stats = pd.DataFrame(rows), pd.DataFrame(scoring)
    read = compare_route_forecasts(frame, stats, season=2026).set_index('policy')
    assert read.targets.eq(6).all()
    assert read.loc['Four-game actual', 'fd'] == 7
    assert read.loc['Four-game expected', 'fd'] == 9
    stats.loc[4, 'rec_yards_gained_exp'] = 99
    pd.testing.assert_frame_equal(read, compare_route_forecasts(frame, stats, season=2026).set_index('policy'))
    frame.loc[3, 'source_updated'] = '2026-10-05T12:00-04:00'
    assert compare_route_forecasts(frame, stats, season=2026).empty
