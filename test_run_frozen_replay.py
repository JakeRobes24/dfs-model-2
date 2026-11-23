from io import BytesIO
import json
from zipfile import ZipFile

import pandas as pd
import pytest

from run_frozen_replay import run
from slate_replay_capture import capture_pool
from test_slate_results import DAY, box, pool


def test_archive_is_written_only_once_official_games_are_final(tmp_path, monkeypatch):
    roster = pool().iloc[:1].assign(fanduel_name='Chris Cenac', fanduel_id='123-248943',
                                    eligible=True, prelock_status='', prelock_starter='',
                                    projected_minutes=19, projected_fd_points=18,
                                    minutes_method='consensus', projection_method='minutes')
    schedule = [dict(awayTeam={'teamTricode': 'DET'}, homeTeam={'teamTricode': 'NOP'},
                     gameTimeUtc='2026-11-19T00:00:00Z')]
    frozen = capture_pool(roster, pd.DataFrame(), schedule, DAY, '2026-11-18T23:00:00Z',
                          ('a' * 64, 'b' * 64))
    quote = dict(stat='Points', bookmaker='book', line=10, daily_stat=12,
                 quoted_at='2026-11-18T22:55:00Z', fair_over_pct=55)
    frozen['replay_player_props_json'] = json.dumps([
        quote, dict(quote, bookmaker='second', line=11),
        dict(quote, stat='Rebounds', line=3.5, daily_stat=None),
        dict(quote, stat='Assists', quoted_at='2026-11-18T23:05:00Z'),
    ])
    source = tmp_path / 'pool.csv'
    output = tmp_path / 'review.zip'
    frozen.to_csv(source, index=False)
    monkeypatch.setattr('run_frozen_replay.collect_final_boxes', lambda day, games: [])
    assert run(source, DAY, output)['status'] == 'waiting_for_verified_final_box_scores'
    assert not output.exists()

    final = box()
    final['awayTeam']['players'][0].update(firstName='Chris', familyName='Cenac Jr.')
    monkeypatch.setattr('run_frozen_replay.collect_final_boxes', lambda day, games: [(final, 'NBA box')])
    assert run(source, DAY, output)['player_outcomes'] == {'played': 1}
    with ZipFile(output) as archive:
        replay = pd.read_csv(BytesIO(archive.read('player_replay.csv')))
        assert replay.actual_points.iloc[0] == 20.3
        assert replay.daily_points.iloc[0] == 18
        assert 'projection_comparison.csv' in archive.namelist()
        diagnostic = pd.read_csv(BytesIO(archive.read('projection_error_decomposition.csv')))
        assert set(diagnostic.forecast) == {'DAILY', 'Adjusted'}
        assert set(diagnostic.fanduel_id.astype(str)) == {'123-248943'}
        assert (diagnostic.minutes_contribution + diagnostic.rate_contribution - diagnostic.point_error).abs().max() < 1e-8
        diagnostic_summary = pd.read_csv(BytesIO(archive.read('projection_error_decomposition_summary.csv')))
        assert diagnostic_summary.players.eq(1).all()
        grouped = pd.read_csv(BytesIO(archive.read('adjustment_comparison.csv')))
        assert grouped['Minutes method'].eq('consensus').all()
        props = pd.read_csv(BytesIO(archive.read('player_prop_review.csv')))
        assert len(props) == 3
        props = props.loc[props.bookmaker.eq('book')].set_index('stat')
        assert list(props.index) == ['Points', 'Rebounds']
        assert props.loc['Points', 'outcome'] == 'Push'
        assert props.loc['Points', 'daily_absolute_error'] == 2
        assert pd.isna(props.loc['Points', 'brier'])
        assert props.loc['Rebounds', 'actual'] == 4
        assert props.loc['Rebounds', 'brier'] == pytest.approx(0.45 ** 2)
        assert pd.isna(props.loc['Rebounds', 'daily_absolute_error'])
        summary = pd.read_csv(BytesIO(archive.read('player_prop_summary.csv'))).iloc[0]
        assert summary.stat == 'Points' and summary.paired_players == 1 and summary.median_books == 2
        assert summary.daily_mae == 2 and summary.mean_threshold_distance == 0.5
    with pytest.raises(FileExistsError, match='new output path'):
        run(source, DAY, output)
