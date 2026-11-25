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
    frozen['propsims_distribution_json'] = json.dumps([dict(
        source='https://propsims.com/nba/dfs/', observed_at='2026-11-18T22:55:00Z',
        fd_median=21, fd_p10=10, fd_p85=34, play_probability=.8, conditional_fd_median=23)])
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
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['diagnostic_coverage']['verified_played'] == 1
        assert manifest['diagnostic_coverage']['paired_played_diagnostics'] == 1
        assert manifest['diagnostic_coverage']['paired_played_coverage_pct'] == 100
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
        coverage = pd.read_csv(BytesIO(archive.read('projection_error_decomposition_coverage.csv'))).iloc[0]
        assert coverage.eligible_players == 1
        assert coverage.verified_played == 1
        assert coverage.paired_played_diagnostics == 1
        assert coverage.paired_played_coverage_pct == 100
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
        distribution = pd.read_csv(BytesIO(archive.read('propsims_distribution_review.csv'))).iloc[0]
        assert distribution.actual_points == pytest.approx(20.3)
        assert distribution.median_absolute_error == pytest.approx(.7)
        assert distribution.play_brier == pytest.approx(.04)
        assert distribution.inside_interval
        distribution_summary = pd.read_csv(BytesIO(archive.read('propsims_distribution_summary.csv'))).iloc[0]
        assert distribution_summary.paired_points_count == 1
        assert distribution_summary.interval_count == 1
        summary = pd.read_csv(BytesIO(archive.read('player_prop_summary.csv'))).iloc[0]
        assert summary.stat == 'Points' and summary.paired_players == 1 and summary.median_books == 2
        assert summary.daily_mae == 2 and summary.mean_threshold_distance == 0.5
    with pytest.raises(FileExistsError, match='new output path'):
        run(source, DAY, output)


def test_distribution_review_excludes_leakage_unknown_outcomes_and_invalid_quantiles():
    from nba_distribution_review import review_distribution, summarize_distribution, SOURCE
    estimate = dict(source=SOURCE, observed_at='2026-11-18T22:00:00Z', fd_median=20,
                    fd_p10=10, fd_p85=35, play_probability=.75, conditional_fd_median=24)
    base = dict(eligible=True, verified_outcome='played', actual_points=-1,
                daily_points=19, adjusted_fd_points=21,
                replay_captured_at_utc='2026-11-18T23:00:00Z',
                replay_cutoff_utc='2026-11-19T00:00:00Z',
                replay_before_full_slate_tip=True, replay_timing='before_scheduled_tip',
                propsims_distribution_json=json.dumps([estimate]))
    data = pd.DataFrame([
        dict(base, fanduel_id='100-1'),
        dict(base, fanduel_id='100-2', verified_outcome='did_not_play', actual_points=None),
        dict(base, fanduel_id='100-3', verified_outcome='needs_review'),
        dict(base, fanduel_id='100-4', propsims_distribution_json=json.dumps([
            dict(estimate, observed_at='2026-11-18T23:01:00Z')])),
        dict(base, fanduel_id='100-5', propsims_distribution_json=json.dumps([
            dict(estimate, observed_at='2026-11-18T15:00:00Z')])),
        dict(base, fanduel_id='100-6', eligible=False),
        dict(base, fanduel_id='100-7', propsims_distribution_json=json.dumps([
            dict(estimate, fd_p10=25, fd_p85=15)])),
        dict(base, fanduel_id='100-8', replay_before_full_slate_tip=False),
        dict(base, fanduel_id='100-9', propsims_distribution_json=json.dumps([estimate, estimate])),
    ])
    details = review_distribution(data).set_index('fanduel_id')
    assert list(details.index) == ['100-1','100-2','100-7']
    assert details.loc['100-1','actual_points'] == -1
    assert details.loc['100-2','actual_points'] == 0
    assert details.loc['100-2','play_brier'] == pytest.approx(.75**2)
    assert pd.isna(details.loc['100-2','conditional_absolute_error'])
    assert details.loc['100-1','p10_pinball'] == pytest.approx(9.9)
    assert pd.isna(details.loc['100-7','fd_p10'])
    summary = summarize_distribution(details.reset_index()).iloc[0]
    assert summary.verified_forecasts == 3
    assert summary.interval_count == 2 and summary.conditional_played_count == 2
    assert summary.verified_dnp == 1
    assert review_distribution(data.drop(columns='propsims_distribution_json')).empty
