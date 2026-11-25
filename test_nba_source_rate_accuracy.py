import json
from datetime import date

import pandas as pd
import pytest

from nba_source_rate_accuracy import review_source_rates
from slate_research import PROPSIMS


def sample():
    day = '2026-11-24'
    stamp = day+'T19:00:00Z'
    record = dict(source=PROPSIMS, family='propsims', points=36, paired_minutes=30,
                  observed_at=stamp)
    base = dict(slate_date=day, fanduel_id='137128-1', eligible=True, verified_outcome='played',
                actual_points=30, actual_minutes=30, daily_points=25, daily_minutes=25,
                adjusted_fd_points=30, adjusted_minutes=25, replay_captured_at_utc=day+'T20:00:00Z',
                replay_cutoff_utc=day+'T23:00:00Z', replay_timing='before_scheduled_tip',
                replay_before_full_slate_tip=True, projection_sources_json=json.dumps([record]))
    return base, record


def test_same_record_rates_and_matched_baselines():
    base, record = sample()
    details, daily, summary = review_source_rates(pd.DataFrame([base]),date(2026,11,25))
    assert len(details) == len(daily) == len(summary) == 1
    assert details.iloc[0].source_fppm == pytest.approx(1.2)
    assert details.iloc[0].actual_fppm == 1
    assert summary.iloc[0].equal_day_rate_mae == pytest.approx(.2)
    assert summary.iloc[0].equal_day_edge_vs_daily == pytest.approx(-.2)
    assert summary.iloc[0].equal_day_edge_vs_reviewed == pytest.approx(0)


def test_reject_brief_appearances_dnp_stale_and_unpaired_forecasts():
    base, record = sample()
    for row in [dict(base,actual_minutes=9),dict(base,verified_outcome='did_not_play'),
                dict(base,projection_sources_json=json.dumps([dict(record,paired_minutes=9)])),
                dict(base,projection_sources_json=json.dumps([dict(record,observed_at='2026-11-24T12:00:00Z')])),
                dict(base,projection_sources_json=json.dumps([dict(record,paired_minutes=None)]))]:
        details, _, _ = review_source_rates(pd.DataFrame([row]),date(2026,11,25))
        assert details.empty


def test_minutes_from_newer_separate_record_not_borrowed():
    base, record = sample()
    note = dict(source=PROPSIMS, independent_group='propsims', official=False,
                observed_at='2026-11-24T19:30:00Z',minutes=34)
    row = dict(base,replay_evidence_json=json.dumps([note]))
    details, _, _ = review_source_rates(pd.DataFrame([row]),date(2026,11,25))
    assert details.empty


def test_fixed_minutes_counterfactual_holds_playing_time_constant():
    from nba_source_rate_accuracy import fixed_minutes_rate_review
    base, record = sample()
    base.update(adjusted_fd_points=25, adjusted_minutes=25)
    details, _, _ = review_source_rates(pd.DataFrame([base]), date(2026,11,25))
    assert details.iloc[0].source_rate_reviewed_minutes_fd == pytest.approx(30)
    assert details.iloc[0].daily_rate_reviewed_minutes_fd == pytest.approx(25)
    daily, summary = fixed_minutes_rate_review(details)
    assert daily.iloc[0].paired_players == 1
    assert daily.iloc[0].source_rate_mae == pytest.approx(0)
    assert daily.iloc[0].daily_rate_mae == pytest.approx(5)
    assert summary.iloc[0].equal_day_edge_vs_reviewed == pytest.approx(5)
    assert summary.iloc[0].days_better_than_reviewed == 1
    _, empty = fixed_minutes_rate_review(details.assign(reviewed_fd=None))
    assert empty.empty
    with pytest.raises(ValueError, match='unique'):
        fixed_minutes_rate_review(pd.concat([details,details]))
