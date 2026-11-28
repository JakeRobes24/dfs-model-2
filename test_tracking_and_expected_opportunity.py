from datetime import date

import pandas as pd
import pytest

from nba_tracking_challenge import (TRACKING_COLUMNS, compare_tracking_conversion,
                                   join_assist_tracking, nba_house_potential_assists)
from nfl_expected_opportunity_validation import compare_expected_opportunity


def test_public_nba_tracking_log_requires_oriented_game_and_matching_box_stats():
    headers = ''.join(f'<th>{field}</th>' for field in TRACKING_COLUMNS)
    cells = ''.join(f'<td>{value}</td>' for value in (34, 7, 16, 11, 16, 84, 22, 69, 1, 1))
    raw = (f'<h1>Josh Giddey</h1><table><thead><tr>{headers}</tr></thead>'
           f'<tbody><tr><td><a href="/game/2026-11-25/chi-at-cha">Game</a></td>{cells}</tr></tbody></table>')
    row, = nba_house_potential_assists(raw)
    official = pd.DataFrame([dict(row, game_id='123', nba_id='22')]).drop(columns='potential')
    source = pd.DataFrame([row])
    assert join_assist_tracking(official, source).potential.tolist() == [16]
    assert join_assist_tracking(official, source.assign(assists=8)).potential.isna().all()
    assert join_assist_tracking(official, pd.concat([source, source])).potential.isna().all()
    with pytest.raises(ValueError, match='one NBA House'):
        nba_house_potential_assists(raw.replace('Pot. ast', 'Projected'))


def test_tracking_conversion_uses_only_prior_chances_and_keeps_exact_support():
    schedule = [(date(2026, 11, i).isoformat(), str(i), 'BOS', 'NYK') for i in range(1, 6)]
    rows = pd.DataFrame([dict(date=day, game_id=game, team='BOS', nba_id='202',
                              minutes=30, rebounds=5, rebound_chances=10)
                         for day, game, *_ in schedule])
    result = compare_tracking_conversion(rows, schedule, channel='rebounds')
    assert len(result) == 4 and result.game_id.tolist() == ['5']*4
    assert result.prediction.eq(5).all()
    changed = rows.copy()
    changed.loc[4, ['rebounds', 'rebound_chances']] = [12, 25]
    assert compare_tracking_conversion(changed, schedule, channel='rebounds').prediction.eq(5).all()
    assert compare_tracking_conversion(rows.drop(1), schedule, channel='rebounds').empty


def test_expected_nfl_components_share_known_rows_and_never_use_target_expectation():
    workload = pd.DataFrame([dict(gsis_id='gsis1', team='DET', game_id=str(i), week=i, position='RB',
                                  team_game_number=i, gameday=f'2026-10-{i:02}', carries=2, targets=3,
                                  rushing_yards=12, receiving_yards=20) for i in range(1, 6)])
    source = pd.DataFrame([dict(season=2026, player_id='gsis1', posteam='DET', game_id=str(i), week=i,
                               position='RB', rec_attempt=3, rush_attempt=2, rec_yards_gained=20,
                               rush_yards_gained=12, receptions=2, rec_touchdown=0, rec_two_point_conv=0,
                               rec_yards_gained_exp=25., receptions_exp=2., rec_touchdown_exp=.5,
                               rec_two_point_conv_exp=0, rush_yards_gained_exp=20., rush_touchdown=0,
                               rush_touchdown_exp=.1, rush_two_point_conv=0, rush_two_point_conv_exp=0)
                           for i in range(1, 6)])
    result, _ = compare_expected_opportunity(workload, source, season=2026)
    receiving = result.loc[result.channel.eq('receiving')].set_index('policy')
    assert receiving.loc['Actual scoring average', 'forecast'] == 3
    assert receiving.loc['Expected scoring average', 'forecast'] == 6.5
    changed = source.copy()
    changed.loc[4, 'rec_yards_gained_exp'] = 90
    pd.testing.assert_frame_equal(result, compare_expected_opportunity(workload, changed, season=2026)[0])
    missing = source.drop(1)
    assert compare_expected_opportunity(workload, missing, season=2026)[0].empty
    ambiguous = pd.concat([source, source.iloc[[1]].assign(position='WR')])
    assert compare_expected_opportunity(workload, ambiguous, season=2026)[0].empty


def test_missing_unrelated_rebound_chances_do_not_discard_valid_assists():
    headers=''.join(f'<th>{field}</th>' for field in TRACKING_COLUMNS)
    def html(values):
        cells=''.join(f'<td>{value}</td>' for value in values)
        return (f'<h1>Jordan Hawkins</h1><table><thead><tr>{headers}</tr></thead>'
                f'<tbody><tr><td><a href="/game/2026-11-08/phi-at-chi">Game</a></td>{cells}</tr></tbody></table>')
    values=[17,1,2,0,'–',21,6,15,2,0]
    row,=nba_house_potential_assists(html(values))
    assert row['potential']==2 and row['rebounds']==0
    official=pd.DataFrame([dict(row,game_id='123',nba_id='22')]).drop(columns='potential')
    source=pd.DataFrame([row])
    assert join_assist_tracking(official,source).potential.tolist()==[2]
    assert join_assist_tracking(official.assign(rebounds=1),source).potential.isna().all()
    for field,value in ((0,4),(1,3),(2,'–'),(3,'–')):
        changed=values.copy()
        changed[field]=value
        assert nba_house_potential_assists(html(changed))==[]
