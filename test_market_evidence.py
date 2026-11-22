from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from market_evidence import fair_over_probability, game_market_evidence


def test_market_matches_exact_game_and_rejects_future_or_stale_quotes():
    now = datetime(2026, 11, 21, 18, tzinfo=ZoneInfo('America/New_York'))
    game = dict(away_team='Boston Celtics', home_team='Sacramento Kings',
                commence_time='2026-11-22T03:00:00Z')
    markets = [
        dict(key='totals', outcomes=[dict(name='Over', point=220.5, price=1.8),
                                     dict(name='Under', point=220.5, price=2.1)]),
        dict(key='spreads', outcomes=[dict(name='Boston Celtics', point=-4.5),
                                      dict(name='Sacramento Kings', point=4.5)]),
    ]
    game['bookmakers'] = [dict(key=key, last_update=stamp, markets=markets) for key, stamp in [
        ('fresh', '2026-11-21T22:55:00Z'), ('future', '2026-11-21T23:05:00Z'),
        ('stale', '2026-11-21T20:59:00Z')]]
    result = game_market_evidence([game], now.date(), now, {'SAC@BOS'}).iloc[0]
    assert result.bookmakers == 1
    assert result.implied_home == 108
    assert result.implied_away == 112.5
    assert result.fair_over_pct == pytest.approx(100 * fair_over_probability(1.8, 2.1))
    assert game_market_evidence([game, game], now.date(), now, {'BOS@SAC'}).empty
    assert game_market_evidence([game], now.date(), now, {'BOS@NYK'}).empty


def test_props_require_verified_player_scope_and_two_way_same_line():
    import pandas as pd

    from market_evidence import player_market_evidence

    now = datetime(2026, 11, 21, 18, tzinfo=ZoneInfo('America/New_York'))
    pool = pd.DataFrame([dict(game='BOS@SAC', fanduel_name='Test Player', fanduel_id='1')])
    quotes = [dict(description='Test Player', name='Over', point=19.5, price=1.8),
              dict(description='Test Player', name='Under', point=19.5, price=2.1)]
    event = dict(away_team='Boston Celtics', home_team='Sacramento Kings',
                 commence_time='2026-11-22T03:00:00Z',
                 bookmakers=[dict(key='book', last_update='2026-11-21T22:55:00Z',
                                  markets=[dict(key='player_points', outcomes=quotes)])])
    matched = player_market_evidence([event], now.date(), now, pool)
    assert matched.iloc[0].fanduel_id == '1'
    assert matched.iloc[0].line == 19.5
    assert matched.iloc[0].fair_over_pct == pytest.approx(100 * fair_over_probability(1.8, 2.1))
    assert player_market_evidence([event], now.date(), now, pd.concat([pool, pool])).empty
    assert player_market_evidence([event], now.date(), now, pool.assign(game='BOS@NYK')).empty
    quotes[1]['point'] = 20.5
    assert player_market_evidence([event], now.date(), now, pool).empty
