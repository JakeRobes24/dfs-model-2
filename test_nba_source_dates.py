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
