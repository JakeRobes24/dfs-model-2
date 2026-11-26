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

def test_fixed_rate_shrinkage_uses_common_sample_and_never_changes_minutes():
    from nba_source_rate_accuracy import fixed_rate_shrinkage_review
    base, record = sample()
    base.update(adjusted_fd_points=25, adjusted_minutes=25)
    details, _, _ = review_source_rates(pd.DataFrame([base]), date(2026,11,25))
    original = details.copy(deep=True)
    daily, summary = fixed_rate_shrinkage_review(details)
    assert daily.independent_weight.tolist() == [0., .2, .4, 1.]
    assert daily.paired_players.tolist() == [1,1,1,1]
    assert daily.fd_mae.tolist() == pytest.approx([5,4,3,0])
    assert daily.fppm_mae.tolist() == pytest.approx([0,.04,.08,.2])
    assert summary.equal_day_fd_edge.tolist() == pytest.approx([0,1,2,5])
    pd.testing.assert_frame_equal(details, original)
    assert fixed_rate_shrinkage_review(details.assign(reviewed_minutes=None))[0].empty
    assert fixed_rate_shrinkage_review(details.assign(actual_minutes=9))[0].empty
    with pytest.raises(ValueError, match='unique'):
        fixed_rate_shrinkage_review(pd.concat([details,details]))
    with pytest.raises(ValueError, match='disagree'):
        fixed_rate_shrinkage_review(details.assign(source_rate_reviewed_minutes_fd=31))


def test_fixed_rate_shrinkage_weights_dates_equally_and_does_not_select_winner():
    from nba_source_rate_accuracy import fixed_rate_shrinkage_review
    base, record = sample()
    base.update(adjusted_fd_points=25, adjusted_minutes=25)
    details, _, _ = review_source_rates(pd.DataFrame([base]),date(2026,11,25))
    # Day one has one player and a 5-point gain. Day two has two
    # players and a 5-point loss; dates, not row counts, receive equal weight.
    extra = details.assign(slate_date='2026-11-23', actual_fd_points=25)
    all_rows = pd.concat([details, extra, extra.assign(fanduel_id='137127-2')])
    _, summary = fixed_rate_shrinkage_review(all_rows)
    full = summary.loc[summary.independent_weight.eq(1.)].iloc[0]
    assert full.dates == 2
    assert full.paired_players == 3
    assert full.equal_day_fd_edge == pytest.approx(0)
    assert full.improved_dates == 1


def test_paired_attribution_separates_minutes_from_scoring_rate():
    from nba_source_rate_accuracy import paired_rate_attribution

    base, _ = sample()
    base.update(nba_source='NBA official box score', adjusted_fd_points=25)
    details, _, _ = review_source_rates(pd.DataFrame([base]), date(2026, 11, 25))
    original = details.copy(deep=True)
    daily, summary = paired_rate_attribution(details)
    rows = daily.set_index('policy')
    assert len(summary) == 5
    assert rows.paired_players.eq(1).all()
    assert rows.loc['Reviewed', 'fd_mae'] == pytest.approx(5)
    assert rows.loc['Provider minutes only', 'fd_mae'] == pytest.approx(0)
    assert rows.loc['Provider scoring rate only', 'fd_mae'] == pytest.approx(0)
    assert rows.loc['Provider scoring rate only', 'fppm_mae'] == pytest.approx(.2)
    assert rows.loc['Provider minutes and rate', 'fd_mae'] == pytest.approx(6)
    assert rows.loc['Provider minutes and rate', 'players_worsened'] == 1
    pd.testing.assert_frame_equal(details, original)


def test_paired_attribution_uses_one_common_sample_and_balances_dates():
    from nba_source_rate_accuracy import paired_rate_attribution

    base, _ = sample()
    base.update(nba_source='NBA official box score', adjusted_fd_points=25)
    first, _, _ = review_source_rates(pd.DataFrame([base]), date(2026, 11, 25))
    other = first.assign(slate_date='2026-11-23', actual_fd_points=25)
    details = pd.concat([first, other, other.assign(fanduel_id='137127-2'),
                         first.assign(fanduel_id='137128-2', nba_source=''),
                         first.assign(fanduel_id='137128-3', daily_minutes=None)])
    daily, summary = paired_rate_attribution(details)
    assert daily.groupby('slate_date').paired_players.nunique().eq(1).all()
    assert summary.paired_players.eq(3).all()
    provider_time = summary.set_index('policy').loc['Provider minutes only']
    assert provider_time.equal_day_fd_edge == pytest.approx(0)
    with pytest.raises(ValueError, match='one row'):
        paired_rate_attribution(pd.concat([first, first]))
    with pytest.raises(ValueError, match='reproduce'):
        paired_rate_attribution(first.assign(source_fd_points=40))
