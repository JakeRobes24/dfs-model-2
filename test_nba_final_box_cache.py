from datetime import date, timedelta
from unittest.mock import patch

from nba_final_box_cache import FinalBoxCache
from slate_research import recent_boxscores


def test_cache_is_bounded_expiring_and_isolates_mutation():
    day = date(2026, 11, 24)
    clock = [0.]
    cache = FinalBoxCache(max_entries=1, ttl_seconds=10, clock=lambda: clock[0])
    key = (day, '0022600001', 'BOS', 'NYK')
    rows = [dict(team=team, game='BOS@NYK', game_date=day, minutes=30) for team in ('BOS','NYK')]
    cache.put(key, rows[:1])
    assert cache.get(key) is None
    cache.put(key, rows)
    rows[0]['minutes'] = 99
    assert cache.get(key)[0]['minutes'] == 30
    cached = cache.get(key)
    cached[0]['minutes'] = 0
    assert cache.get(key)[0]['minutes'] == 30
    assert cache.get((day, '0022600001', 'NYK', 'BOS')) is None
    clock[0] = 10.
    assert cache.get(key) is None
    cache.put(key, rows)
    key2 = (day, '0022600002', 'BOS','NYK')
    cache.put(key2, rows)
    assert cache.get(key) is None and cache.get(key2) is not None


def test_recent_rotation_windows_reuse_only_successful_matching_final_boxes():
    slate = date(2026,11,25)
    day = slate-timedelta(days=1)
    item = dict(awayTeam={'teamTricode':'BOS'}, homeTeam={'teamTricode':'NYK'},
                gameId='0022600001', gameStatus=3)
    rows = [dict(team=t, game='BOS@NYK', game_date=day, minutes=30) for t in ('BOS','NYK')]
    cache = FinalBoxCache()
    with patch('slate_research.games_for_date', return_value=[item]) as schedule, \
         patch('slate_research.nba_page', return_value={'game': {'gameId':item['gameId']}}) as box, \
         patch('slate_research.read_box', side_effect=[[], rows]):
        first, status = recent_boxscores(slate, {'BOS@NYK'},days_back=1,box_cache=cache)
        assert not first and '0/1 final' in status
        second, status = recent_boxscores(slate, {'BOS@NYK'},days_back=1,box_cache=cache)
        assert second == rows and '0 recently' in status
        third, status = recent_boxscores(slate, {'BOS@NYK'},days_back=1,box_cache=cache)
        assert third == rows and '1 recently' in status
        assert schedule.call_count == 3 and box.call_count == 2
