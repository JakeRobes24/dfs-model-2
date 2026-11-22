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
