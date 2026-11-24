import pandas as pd
import pytest

from nba_dependence import walk_forward_dependence


def archived_day(day, contest, errors):
    games = ['BOS@NYK', 'SAC@GSW', 'MIN@DEN', 'TOR@DET', 'MIA@ORL']
    rows = []
    for game in games:
        for team, error in zip([team for team in game.split('@') for _ in range(2)], errors):
            rows.append(dict(slate_date=day, fanduel_id=f'{contest}-{len(rows)}', team=team, game=game,
                             eligible=True, daily_minutes=25, daily_points=25, actual_minutes=25,
                             actual_points=25 + error))
    return pd.DataFrame(rows)


def test_walk_forward_detects_teammate_and_opponent_differences():
    earlier = archived_day('2026-11-18', '123', [5, 5, -5, -5])
    later = archived_day('2026-11-20', '789', [5, 5, -5, -5])
    report = walk_forward_dependence(pd.concat([later, earlier])).set_index('relationship')
    assert set(report.slate_date) == {'2026-11-20'}
    assert report.training_games.eq(5).all() and report.test_games.eq(5).all()
    assert report.loc['teammate', 'prior_cross_product'] == pytest.approx(1)
    assert report.loc['opponent', 'prior_cross_product'] == pytest.approx(-1)
    assert report.prior_mse.eq(0).all() and report.zero_mse.eq(1).all()


def test_walk_forward_omits_games_with_multiple_saved_contests_or_missing_box_results():
    earlier = archived_day('2026-11-18', '123', [5, 5, -5, -5])
    later = archived_day('2026-11-20', '789', [5, -5, 5, -5])
    duplicate_game = later.iloc[:4].copy()
    duplicate_game['fanduel_id'] = duplicate_game.fanduel_id.str.replace('789-', '456-')
    later.loc[later.index[4], 'actual_minutes'] = 0
    report = walk_forward_dependence(pd.concat([earlier, later, duplicate_game]))
    assert report.test_games.eq(3).all()
    assert (report.prior_mse > report.zero_mse).all()
    assert walk_forward_dependence(later).empty


def test_reviewed_dependence_uses_adjusted_errors_and_verified_prior_dates():
    from nba_dependence import reviewed_dependence_evidence

    def verified(day, contest):
        frame = archived_day(day, contest, [5, -5, 5, -5])
        # DAILY errors alternate within teams; reviewed errors align within teams.
        return frame.assign(adjusted_fd_points=frame.actual_points - [5, 5, -5, -5] * 5,
            adjusted_minutes=25, verified_outcome='played', nba_source='NBA final box',
            replay_before_full_slate_tip=True, replay_timing='before_scheduled_tip',
            replay_captured_at_utc=day+'T18:00:00Z', replay_cutoff_utc=day+'T23:00:00Z')

    first = verified('2026-11-18', '123')
    second = verified('2026-11-20', '456')
    same = verified('2026-11-24', '789')
    bad = verified('2026-11-19', '111').assign(replay_before_full_slate_tip=False)
    details, summary = reviewed_dependence_evidence(pd.concat([first, second, same, bad]), '2026-11-24')
    assert set(details.slate_date) == {'2026-11-20'}
    assert details.training_games.eq(5).all()
    assert details.set_index('relationship').loc['teammate','prior_cross_product'] == pytest.approx(1)
    assert details.set_index('relationship').loc['opponent','prior_cross_product'] == pytest.approx(-1)
    assert summary.status.eq('Insufficient held-out evidence').all()
    assert summary.prior_mse.eq(0).all()
    assert summary.zero_mse.eq(1).all()
    assert reviewed_dependence_evidence(pd.concat([first, first, second]), '2026-11-24')[0].empty
    assert reviewed_dependence_evidence(pd.concat([first.assign(nba_source=''), second]), '2026-11-24')[0].empty
