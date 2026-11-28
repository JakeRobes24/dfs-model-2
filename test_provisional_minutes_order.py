"""Regression: agreeing source order must not change NBA research conclusions."""
from datetime import datetime, timezone
from itertools import permutations

import pandas as pd
import pytest

from slate_research import NBA_HOUSE, PROPSIMS, ROTOGRINDERS, score_slate


def inputs():
    pool = pd.DataFrame([dict(fanduel_id='100-1', fanduel_name='Example Player',
                              injury_flag='', projected_minutes=26., projected_fd_points=31.2)])
    history = pd.DataFrame(columns=['player', 'season_mpg', 'last5_mpg', 'last10_mpg', 'history_games'])
    def note(source, group, minutes):
        return dict(fanduel_id='100-1', source=source, independent_group=group,
                    observed_at='2026-11-24T20:00:00Z', official=False,
                    status='', starter='', role='', minutes=minutes)
    return pool, history, note


def test_agreeing_minutes_center_and_research_flag_ignore_source_order():
    pool, history, note = inputs()
    notes = [note(NBA_HOUSE,'nba-house',30.), note(PROPSIMS,'propsims',32.5)]
    cutoff = datetime(2026,11,24,21,tzinfo=timezone.utc)
    for order in permutations(notes):
        scored, _ = score_slate(pool,history,list(order),[],cutoff)
        row = scored.iloc[0]
        assert row.independent_minutes == pytest.approx(31.25)
        assert row.adjusted_minutes == pytest.approx(31.25)
        assert row.adjusted_fd_points == pytest.approx(37.5)
        assert row.minutes_method == 'prelock_independent_consensus'
        assert 'Review source disagreement' in row.research_attention


def test_preserve_single_source_and_distinct_consensus_thresholds():
    pool, history, note = inputs()
    cutoff = datetime(2026,11,24,21,tzinfo=timezone.utc)
    single, _ = score_slate(pool,history,[note(NBA_HOUSE,'nba-house',30.)],[],cutoff)
    assert single.iloc[0].independent_minutes == 30.
    assert single.iloc[0].adjusted_minutes == 26.
    split, _ = score_slate(pool,history,[note(NBA_HOUSE,'nba-house',30.),
                                         note(PROPSIMS,'propsims',33.5)],[],cutoff)
    assert pd.isna(split.iloc[0].independent_minutes)
    assert split.iloc[0].adjusted_minutes == pytest.approx(31.75)


def test_three_sources_use_middle_estimate_not_first():
    pool, history, note = inputs()
    cutoff = datetime(2026,11,24,21,tzinfo=timezone.utc)
    notes = [note(NBA_HOUSE,'nba-house',30.), note(PROPSIMS,'propsims',32.5),
             note(ROTOGRINDERS,'rotogrinders',31.)]
    for order in permutations(notes):
        scored, _ = score_slate(pool,history,list(order),[],cutoff)
        assert scored.iloc[0].independent_minutes == 31.
        assert scored.iloc[0].adjusted_minutes == 31.
