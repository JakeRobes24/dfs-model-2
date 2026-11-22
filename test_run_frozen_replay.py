from io import BytesIO
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
        grouped = pd.read_csv(BytesIO(archive.read('adjustment_comparison.csv')))
        assert grouped['Minutes method'].eq('consensus').all()
    with pytest.raises(FileExistsError, match='new output path'):
        run(source, DAY, output)
