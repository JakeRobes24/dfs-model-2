from datetime import date
from io import BytesIO
import json
from unittest.mock import patch

import pandas as pd
import pytest

from history_intake import load_slate_packet, make_submission
from slate_results import collect_final_boxes, compare_results
from slate_results_ui import lineup_review

DAY = date(2026, 11, 18)


def player(person, name, **fields):
    first, last = name.split(' ', 1)
    return dict(personId=person, firstName=first, familyName=last, **fields)


def pool():
    return pd.DataFrame([
        dict(fanduel_id=f'123-{number}', fanduel_name=name, team='DET', game=game,
             salary=5000, position='SF', adjusted_fd_points=17, adjusted_minutes=20)
        for number, name, game in [(1, 'Ronald Holland', 'DET@NOP'), (2, 'Same Name', 'DET@NOP'),
                                   (3, 'Missing Player', 'DET@NOP'), (4, 'Other Player', 'DET@BOS')]
    ])


def box():
    return dict(gameId='0022600258', gameStatus=3, gameTimeUTC='2026-11-19T00:00:00Z',
                awayTeam=dict(teamTricode='DET', players=[
                    player(1, 'Ronald Holland II', statistics=dict(minutes='20:30', points=10,
                           reboundsTotal=4, assists=3, steals=1, blocks=0, turnovers=2)),
                    player(2, 'Same Name', comment='DNP - Injury'),
                    player(3, 'Same Name', comment='DNP - Injury'),
                ]), homeTeam=dict(teamTricode='NOP', players=[]))


def test_results_separate_conflict_and_unknown():
    result, finals = compare_results(pool(), DAY, [(box(), 'NBA box')], {'123-1': 21.1})
    assert finals == {'DET/NOP'}
    assert result.outcome.tolist() == ['Played', 'Needs review', 'Needs review', 'Final box unavailable']
    assert result.nba_actual_minutes.iloc[0] == 20.5
    assert result.nba_fd_points.iloc[0] == 20.3
    assert result.recorded_fd_points.iloc[0] == 21.1
    assert result.actual_comparison.iloc[0] == 'Differs'
    assert result.nba_fd_points.iloc[1:].isna().all()


def test_collection_requires_final_correct_game_and_date():
    correct = box()
    with patch('slate_results.games_for_date', return_value=[correct]), patch(
        'slate_results.nba_page', return_value={'game': dict(correct, gameStatus=2)}
    ):
        assert collect_final_boxes(DAY, ('DET/NOP',)) == []
    with patch('slate_results.games_for_date', return_value=[correct]), patch(
        'slate_results.nba_page', return_value={'game': dict(correct, gameTimeUTC='2026-11-20T00:00:00Z')}
    ):
        assert collect_final_boxes(DAY, ('DET/NOP',)) == []
    with patch('slate_results.games_for_date', return_value=[correct]), patch(
        'slate_results.nba_page', return_value={'game': correct}
    ):
        assert collect_final_boxes(DAY, ('DET/NOP',))[0][0] == correct


def test_content_addressed_packet_checks_bytes_and_metadata():
    frame = pool().assign(projected_minutes=20, projected_fd_points=17, injury_flag='', roster_eligibility='SF')
    path, data = make_submission(frame, DAY)
    folder, filename = path.rsplit('/', 1)
    with patch('history_snapshot._request', return_value=BytesIO(data)):
        saved, lineups = load_slate_packet('test', 'a' * 40, folder, filename)
    assert saved.fanduel_id.tolist() == frame.fanduel_id.tolist()
    assert lineups is None
    tampered = json.dumps(dict(json.loads(data), contest_id='456')).encode()
    with patch('history_snapshot._request', return_value=BytesIO(tampered)):
        with pytest.raises(ValueError, match='checksum'):
            load_slate_packet('test', 'a' * 40, folder, filename)


def test_lineup_total_counts_confirmed_dnp_but_requires_all_other_results():
    ids = [f'123-{i}' for i in range(9)]
    lineups = pd.DataFrame({'lineup': 'A', 'fanduel_id': ids})
    results = pd.DataFrame({'fanduel_id': ids, 'projected_fd_points': 11, 'adjusted_fd_points': 10,
                            'nba_fd_points': [10] * 8 + [None], 'outcome': ['Played'] * 8 + ['Did not play']})
    row = lineup_review(lineups, results).iloc[0]
    assert row['NBA box-score FD'] == 80
    assert row['DAILY projection'] == 99
    assert row['Pre-lock projection'] == 90
    assert row['DAILY absolute error'] == 19
    assert row['Pre-lock absolute error'] == 10
    results.loc[0, 'projected_fd_points'] = None
    row = lineup_review(lineups, results).iloc[0]
    assert pd.isna(row['DAILY projection'])
    assert pd.isna(row['Pre-lock absolute error'])
    results.loc[0, 'projected_fd_points'] = 11
    results.loc[8, 'nba_fd_points'] = 5
    results.loc[8, 'outcome'] = 'Needs review'
    summary = lineup_review(lineups, results)
    assert pd.isna(summary.iloc[0]['NBA box-score FD'])
    assert pd.isna(summary.iloc[0]['DAILY absolute error'])
    assert summary.iloc[0]['Players still unresolved'] == 1


def test_new_actuals_preserves_recorded_and_unresolved_scores():
    from slate_results_ui import new_actuals
    results = pd.DataFrame({
        'fanduel_id': ['123-1', '123-2', '123-3', '123-4'],
        'outcome': ['Played', 'Did not play', 'Played', 'Needs review'],
        'nba_source': ['box', 'box', 'box', 'box'],
        'nba_actual_minutes': [20, None, 25, None],
        'nba_fd_points': [22, None, 30, None],
    })
    history = pd.DataFrame({'slate_date': [DAY.isoformat()], 'fanduel_id': ['123-3'],
                            'actual_minutes': [25], 'actual_fd_points': [33]})
    fresh = new_actuals(results, history, DAY)
    assert fresh.fanduel_id.tolist() == ['123-1', '123-2']
    assert fresh.actual_fd_points.tolist() == [22, 0]
    assert 'confirmed did not play' in fresh.actuals_source.iloc[1]


def test_official_components_preserve_zero_and_unknown():
    result,_=compare_results(pool(),DAY,[(box(),'NBA box')],{})
    assert result.loc[0,'nba_steals']==1
    assert result.loc[0,'nba_blocks']==0
    assert result.loc[0,'nba_turnovers']==2
    assert result.loc[1:,'nba_steals'].isna().all()
