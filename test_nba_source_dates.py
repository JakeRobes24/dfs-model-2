import json
from datetime import date

import pandas as pd
import pytest

from nba_source_accuracy import review_source_dates
from slate_research import DFF


def fixture(day, contest, count, forecast, actual=20):
    return [dict(slate_date=day, fanduel_id=f'{contest}-{i}', eligible=True,
                 verified_outcome='played', actual_points=actual, actual_minutes=30,
                 daily_points=25, daily_minutes=30, adjusted_fd_points=23, adjusted_minutes=30,
                 replay_captured_at_utc=f'{day}T20:00:00Z', replay_cutoff_utc=f'{day}T23:00:00Z',
                 replay_timing='before_scheduled_tip', replay_before_full_slate_tip=True,
                 projection_sources_json=json.dumps([dict(source=DFF, family='daily-fantasy-fuel',
                     points=forecast, observed_at=f'{day}T19:00:00Z')]))
            for i in range(count)]


def test_equal_date_accuracy_not_dominated_by_big_slate():
    rows = fixture('2026-11-20',136961,10,20) + fixture('2026-11-24',137128,1,30)
    details, daily, aggregate = review_source_dates(pd.DataFrame(rows),date(2026,11,25))
    assert len(details) == 11 and len(daily) == 2
    result = aggregate.iloc[0]
    assert result.dates == 2 and result.paired_forecasts == 11
    assert result.equal_day_mae == 5
    assert result.equal_day_edge_vs_daily == 0
    assert result.equal_day_edge_vs_reviewed == -2
    assert result.days_better_than_daily == 1
    assert result.days_better_than_reviewed == 1


def test_reject_current_dates_multiple_contests_and_conflicting_duplicates():
    rows = fixture('2026-11-24',137128,1,20)
    target = date(2026,11,25)
    with pytest.raises(ValueError, match='earlier'):
        review_source_dates(pd.DataFrame(rows),date(2026,11,24))
    with pytest.raises(ValueError, match='one verified contest'):
        review_source_dates(pd.DataFrame(rows+fixture('2026-11-24',137139,1,20)),target)
    with pytest.raises(ValueError, match='unique frozen replay'):
        review_source_dates(pd.DataFrame(rows+[dict(rows[0],actual_points=30)]),target)
    details, _, _ = review_source_dates(pd.DataFrame(rows+rows),target)
    assert len(details) == 1


def test_paired_provider_transport_retry_is_bounded_and_never_retries_denied_access():
    from unittest.mock import patch
    from urllib.error import HTTPError, URLError
    from slate_research import fetch_paired_provider, PROPSIMS
    transient = [TimeoutError('timeout'), URLError(ConnectionResetError('reset')),
                 HTTPError(PROPSIMS, 503, 'unavailable', None, None)]
    for failure in transient:
        with patch('slate_research.fetch', side_effect=[failure, b'ok']) as fetch:
            assert fetch_paired_provider(PROPSIMS) == b'ok'
            assert fetch.call_count == 2
    for failure in [HTTPError(PROPSIMS, 403, 'denied', None, None),
                    HTTPError(PROPSIMS, 429, 'rate limited', None, None),
                    ValueError('invalid data'), URLError('certificate error')]:
        with patch('slate_research.fetch', side_effect=failure) as fetch:
            with pytest.raises(type(failure)):
                fetch_paired_provider(PROPSIMS)
            assert fetch.call_count == 1
    with patch('slate_research.fetch', side_effect=TimeoutError('timeout')) as fetch:
        with pytest.raises(TimeoutError):
            fetch_paired_provider(PROPSIMS)
        assert fetch.call_count == 2


def test_propsims_invalid_row_does_not_discard_valid_same_provider_pairs():
    from datetime import datetime
    from unittest.mock import patch
    from slate_research import propsims_research, ET
    now = datetime(2026, 11, 25, 5, tzinfo=ET)
    html = """<h1>NBA DFS projections: Wednesday, November 25</h1>
    <div class="updstamp"><time datetime="2026-11-25T04:01:00-05:00"></time></div>
    <table><tr><td class="player"><a>Masked Player</a><span class="msub">BOS · G vs NYK</span></td>
    <td data-f="fd_p50" data-v="--"></td><td data-f="min_p50" data-v="31"></td></tr>
    <tr><td class="player"><a>Valid Player</a><span class="msub">BOS · G vs NYK</span></td>
    <td data-f="fd_p50" data-v="34.5"></td><td data-f="min_p50" data-v="30"></td></tr></table>"""
    with patch('slate_research.fetch', return_value=html.encode()):
        (notes, points), _ = propsims_research(now.date(), now)
        assert len(notes) == len(points) == 1
        assert notes[0]['player'] == points[0]['player'] == 'Valid Player'
        assert points[0]['points'] == 34.5
        assert points[0]['paired_minutes'] == 30
        assert points[0]['observed_at'] == '2026-11-25T04:01:00-05:00'


def test_rotogrinders_fresh_previous_evening_requires_exact_current_pre_tip_schedule():
    from datetime import datetime, timedelta
    from unittest.mock import patch
    from slate_research import rotogrinders_research, ET
    now = datetime(2026, 11, 25, 1, tzinfo=ET)
    html = """<div><div>FPTS Updated</div><span data-role="localtime" data-value="2026-11-24T23:30:00-05:00"></span></div>
    <option data-field="schedule" data-value="123">2026-11-25 7:00pm (BOS @ NYK)</option>
    <table><thead><tr><th>PLAYER</th><th>TEAM</th><th>OPP</th><th>MINUTES</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TO</th></tr></thead>
    <tbody><tr data-schedule="123"><td><a data-role="modal">Valid Player</a></td><td>BOS</td><td>NYK</td><td>30</td><td>20</td><td>5</td><td>4</td><td>1</td><td>1</td><td>2</td></tr></tbody></table>"""
    with patch('slate_research.fetch', return_value=html.encode()):
        (notes, points), _ = rotogrinders_research(now.date(), now)
        assert len(notes) == len(points) == 1
        assert points[0]['points'] == 36 and points[0]['paired_minutes'] == 30
        assert points[0]['observed_at'] == '2026-11-24T23:30:00-05:00'
        with pytest.raises(ValueError, match='stale'):
            rotogrinders_research(now.date(), now + timedelta(hours=5))
        with pytest.raises(ValueError, match='stale'):
            rotogrinders_research(now.date() - timedelta(days=1), now)
    for invalid in [html.replace('23:30:00-05:00', '23:30:00'),
                    html.replace('2026-11-25 7:00pm', '2026-11-24 7:00pm')]:
        with patch('slate_research.fetch', return_value=invalid.encode()):
            with pytest.raises(ValueError):
                rotogrinders_research(now.date(), now)


def test_minutes_challenger_uses_identical_players_and_excludes_duplicate_families():
    import pandas as pd

    from nba_source_accuracy import compare_minutes_consensus

    def forecast(pid, provider, minutes, date='2026-11-24'):
        return dict(slate_date=date, fanduel_id=pid, provider=provider, metric='Minutes',
                    forecast=minutes, actual=30, reviewed=34, daily=40)

    forecasts = pd.DataFrame([
        forecast('a', 'x', 27), forecast('a', 'y', 31), forecast('b', 'x', 30),
        forecast('a', 'x', 30, '2026-11-25'), forecast('a', 'x', 33, '2026-11-25'),
        forecast('a', 'y', 35, '2026-11-25'),
    ])
    result = compare_minutes_consensus(forecasts).iloc[0]
    assert len(compare_minutes_consensus(forecasts)) == 1
    assert (result.players, result.daily_mae, result.reviewed_mae) == (1, 10, 4)
    assert (result.provider_median_mae, result.half_consensus_mae) == (1, 1.5)
