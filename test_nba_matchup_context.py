from datetime import date, timedelta

import pandas as pd
import pytest

from nba_matchup_context import matchup_context, team_box_context
from slate_research import read_box


def final_game(period=4):
    def club(team, points):
        return dict(teamTricode=team, statistics=dict(fieldGoalsAttempted=90,
                    freeThrowsAttempted=25, reboundsOffensive=12, turnoversTotal=11,
                    points=points), players=[dict(firstName='Test', familyName=team,
                    personId=team, statistics=dict(minutes='30:00'))])
    return dict(period=period, gameStatus=3, gameTimeUTC='2026-11-20T23:00:00Z',
                awayTeam=club('BOS', 110), homeTeam=club('NYK', 100))


def test_pace_overtime_and_defensive_efficiency():
    game = final_game()
    context = team_box_context(game)
    assert context['BOS']['team_pace48'] == pytest.approx(100)
    assert context['BOS']['team_def_rating'] == pytest.approx(100)
    assert context['NYK']['team_def_rating'] == pytest.approx(110)
    overtime = team_box_context(final_game(5))
    assert overtime['BOS']['team_pace48'] == pytest.approx(100 * 48 / 53)
    assert overtime['BOS']['team_def_rating'] == pytest.approx(100)
    assert read_box(game, 'official box')[0]['team_pace48'] == pytest.approx(100)
    del game['homeTeam']['statistics']['reboundsOffensive']
    assert team_box_context(game) == {}
    assert 'team_pace48' not in read_box(game, 'official box')[0]
    assert team_box_context(dict(final_game(), gameStatus=2)) == {}


def test_matchup_context_deduplicates_team_games_and_excludes_target_day():
    slate = date(2026, 11, 24)
    pool = pd.DataFrame([dict(fanduel_id='123', team='BOS', game='BOS@NYK')])
    rows = []
    for age, pace in [(0, 140), (1, 100), (2, 105), (3, 110), (4, 120)]:
        for team in ('BOS','NYK'):
            row = dict(game_date=slate-timedelta(days=age), game='BOS@NYK', team=team,
                       team_pace48=pace, team_off_rating=110,
                       team_def_rating=100 if team=='BOS' else 115, source=f'box {age}')
            rows += [row.copy() for _ in range(10)]
    result = matchup_context(pool, rows, slate).iloc[0]
    assert result.team_games == result.opponent_games == 3
    assert result.descriptive_pace_mean == 105
    assert result.opponent_def_rating == 115
    assert result.matchup_sample == 'Recent context'
    result = matchup_context(pool, [row for row in rows if row['team']=='BOS'], slate).iloc[0]
    assert result.opponent_games == 0
    assert pd.isna(result.descriptive_pace_mean)
    assert result.matchup_sample == 'Small or missing sample'
    conflicting = rows + [dict(rows[20], team_pace48=115)]
    result = matchup_context(pool, conflicting, slate).iloc[0]
    assert result.team_pace48 == pytest.approx((105+110+120)/3)
