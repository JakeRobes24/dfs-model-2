import pandas as pd

from nfl_snap_workload_review import reconcile_final_workload, review_snap_workload


def test_join_uses_both_provider_ids_and_the_final_game_identity():
    schedule = pd.DataFrame([
        dict(game_id='one', week=1, gameday='2026-09-01', home_team='DET', away_team='CHI',
             home_score=21, away_score=17, season=2026, game_type='REG'),
        dict(game_id='two', week=2, gameday='2026-09-08', home_team='DET', away_team='CHI',
             season=2026, game_type='REG'),
    ])
    snaps = pd.DataFrame([
        dict(pfr_player_id='pfr1', player='Name', game_id='one', team='DET', opponent='CHI',
             week=1, season=2026, game_type='REG', position='RB', offense_snaps=40),
        dict(pfr_player_id='pfr2', player='Name', game_id='two', team='DET', opponent='CHI',
             week=2, season=2026, game_type='REG', position='RB', offense_snaps=40),
    ])
    stats = pd.DataFrame([
        dict(player_id='gsis1', game_id='one', team='DET', opponent_team='CHI',
             week=1, season=2026, season_type='REG', carries=10, targets=2, rushing_yards=40, receiving_yards=10),
        dict(player_id='gsis2', game_id='two', team='DET', opponent_team='CHI',
             week=2, season=2026, season_type='REG', carries=8, targets=3, rushing_yards=30, receiving_yards=15),
    ])
    players = pd.DataFrame({'pfr_id': ['pfr1', 'pfr2'], 'gsis_id': ['gsis1', 'gsis2']})
    args = dict(season=2026, cutoff_day='2026-09-30')
    assert reconcile_final_workload(schedule, snaps, stats, players, **args).gsis_id.tolist() == ['gsis1']
    wrong_opponent = stats.assign(opponent_team='DAL')
    assert reconcile_final_workload(schedule, snaps, wrong_opponent, players, **args).empty
    ambiguous = pd.concat([players, pd.DataFrame({'pfr_id': ['pfr1'], 'gsis_id': ['gsis3']})])
    assert reconcile_final_workload(schedule, snaps, stats, ambiguous, **args).empty


def test_snap_challengers_share_target_sample_and_do_not_fill_missing_team_game():
    history = pd.DataFrame([
        dict(gsis_id='id', team='DET', position='RB', gameday=f'2026-09-{i+1:02}',
             team_game_number=i, week=i+1, offense_snaps=30+i, carries=12+i, targets=2+i,
             rushing_yards=40+i, receiving_yards=10+i)
        for i in range(6)
    ])
    report, summary = review_snap_workload(history)
    assert summary.player_games.eq(2).all()
    assert (report.actual != report.forecast).any()
    prior = report.loc[report.date.eq('2026-09-05')]
    changed = history.copy()
    changed.loc[5, ['carries', 'targets', 'rushing_yards', 'receiving_yards']] = 100
    repeated = review_snap_workload(changed)[0]
    pd.testing.assert_frame_equal(prior, repeated.loc[repeated.date.eq('2026-09-05')])
    assert review_snap_workload(history.drop(2))[0].empty
