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
