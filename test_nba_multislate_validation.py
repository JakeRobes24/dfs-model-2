import json
from zipfile import ZipFile

import pandas as pd
import pytest

from nba_multislate_validation import evaluate_archives


def archive(tmp_path, name, contest, *, final=True, rows=None):
    path = tmp_path / name
    manifest = {'status': 'reviewed' if final else 'waiting',
                'slate_date': '2026-11-22', 'contest_id': contest,
                'contest_games': 2, 'verified_final_games': 2 if final else 1}
    if rows is None:
        rows = [dict(fanduel_id=f'{contest}-1', eligible=True, verified_outcome='played',
                     daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
                     daily_points=20, adjusted_fd_points=24, actual_points=25)]
    with ZipFile(path, 'w') as z:
        z.writestr('manifest.json', json.dumps(manifest))
        z.writestr('player_replay.csv', pd.DataFrame(rows).to_csv(index=False))
    return path


def test_paired_multislate_weighted_mae_without_retraining(tmp_path):
    a = archive(tmp_path, 'a.zip', '100')
    b = archive(tmp_path, 'b.zip', '101', rows=[
        dict(fanduel_id='101-1', eligible=True, verified_outcome='played',
             daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
             daily_points=10, adjusted_fd_points=20, actual_points=10),
        dict(fanduel_id='101-2', eligible=True, verified_outcome='played',
             daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
             daily_points=10, adjusted_fd_points=20, actual_points=10),
        dict(fanduel_id='101-3', eligible=True, verified_outcome='needs_review',
             daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
             daily_points=10, adjusted_fd_points=20, actual_points=10),
    ])
    by_slate, summary = evaluate_archives([a, b])
    points = summary.set_index('metric').loc['FanDuel points']
    assert len(by_slate) == 4
    assert points.paired_players == 3
    assert points.weighted_daily_mae == pytest.approx(5 / 3)
    assert points.weighted_adjusted_mae == pytest.approx(21 / 3)
    assert points.slates_adjusted_better == 1
    assert points.slates_adjusted_worse == 1
    assert points.evidence_status == 'descriptive_only_no_release_authorization'


def test_rejects_nonfinal_and_duplicate_slate(tmp_path):
    good = archive(tmp_path, 'good.zip', '100')
    bad = archive(tmp_path, 'bad.zip', '101', final=False)
    with pytest.raises(ValueError, match='fully verified'):
        evaluate_archives([good, bad])
    with pytest.raises(ValueError, match='repeated slate'):
        evaluate_archives([good, good])


def test_rejects_duplicate_player_ids(tmp_path):
    row = dict(fanduel_id='100-1', eligible=True, verified_outcome='played',
               daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
               daily_points=20, adjusted_fd_points=24, actual_points=25)
    path = archive(tmp_path, 'duplicate.zip', '100', rows=[row, row])
    with pytest.raises(ValueError, match='distinct'):
        evaluate_archives([path])


def test_rejects_player_from_another_contest(tmp_path):
    path = archive(tmp_path, 'wrong_contest.zip', '100', rows=[
        dict(fanduel_id='101-1', eligible=True, verified_outcome='played',
             daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
             daily_points=20, adjusted_fd_points=24, actual_points=25),
    ])
    with pytest.raises(ValueError, match='archived contest'):
        evaluate_archives([path])


def test_unresolved_outcomes_never_enter_error_metrics(tmp_path):
    path = archive(tmp_path, 'unresolved.zip', '100', rows=[
        dict(fanduel_id='100-1', eligible=True, verified_outcome='needs_review',
             daily_minutes=30, adjusted_minutes=30, actual_minutes=30,
             daily_points=20, adjusted_fd_points=24, actual_points=25),
    ])
    _, summary = evaluate_archives([path])
    assert summary.paired_players.eq(0).all()
    assert summary.weighted_daily_mae.isna().all()
    assert summary.slates_adjusted_better.eq(0).all()


def test_rejects_no_archives():
    with pytest.raises(ValueError, match='at least one'):
        evaluate_archives([])
