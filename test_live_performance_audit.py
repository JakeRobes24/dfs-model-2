import numpy as np
import pandas as pd
import pytest

from live_performance_audit import (
    compare_saved_rosters, minute_rate_errors, paired_errors, selection_errors,
    validate_pool, walk_forward_blend,
)


def fixture():
    return pd.DataFrame([
        dict(sport='NBA', date='2026-11-24', contest='100', id='100-1', actual=20.,
             daily=18., reviewed=21., salary=5300, exposure=2, actual_minutes=24., minutes=20.),
        dict(sport='NBA', date='2026-11-24', contest='100', id='100-2', actual=22.,
             daily=21., reviewed=23., salary=5500, exposure=0, actual_minutes=30., minutes=31.),
        dict(sport='NBA', date='2026-11-24', contest='100', id='100-3', actual=np.nan,
             daily=10., reviewed=11., salary=3600, exposure=0, actual_minutes=np.nan, minutes=8.),
    ])


def test_matched_rows_and_selection_bias():
    pool = fixture()
    validate_pool(pool)
    scores = paired_errors(pool, ['daily', 'reviewed'])
    assert scores['daily']['n'] == scores['reviewed']['n'] == 2
    assert scores['daily']['bias'] == -1.5
    assert scores['reviewed']['rmse'] == 1
    assert selection_errors(pool, 'reviewed')['matched_bias_gap'] == 0
    with pytest.raises(ValueError, match='Duplicate'):
        validate_pool(pd.concat([pool,pool]))
    with pytest.raises(ValueError, match='exact contest'):
        validate_pool(pool.assign(contest='200'))


def test_minutes_and_rate_attribution_is_signed_and_exact():
    effects = minute_rate_errors(fixture(), 'reviewed', 'minutes')
    assert len(effects) == 2
    assert effects.minute_effect.iloc[0] < 0 < effects.rate_effect.iloc[0]
    np.testing.assert_allclose(effects.minute_effect+effects.rate_effect,effects.reviewed-effects.actual)


def test_incomplete_rosters_preserve_unknown_totals():
    pool = fixture()
    scores = compare_saved_rosters(pool, {'known': ['100-1','100-2'], 'unknown': ['100-1','100-3']},slots=2)
    assert scores[0]['actual'] == 42
    assert scores[1]['actual'] is None and scores[1]['known_slots'] == 1
    with pytest.raises(ValueError,match='Inconsistent archived roster'):
        compare_saved_rosters(pool,{'duplicate': ['100-1','100-1']},slots=2)


def test_blend_never_fits_with_same_or_later_date():
    pool = fixture()
    earlier = pool.assign(date='2026-11-23',actual=pool.daily)
    target = pool.assign(date='2026-11-25')
    forecasts = pd.concat([earlier, pool, target],ignore_index=True)
    result, = walk_forward_blend(forecasts,'daily','reviewed')
    assert 0 < result['fraction_of_reviewed'] < 1
    target.actual += 20
    changed, = walk_forward_blend(pd.concat([earlier, pool, target]),'daily','reviewed')
    assert changed['fraction_of_reviewed'] == result['fraction_of_reviewed']
    assert changed['comparison']['shadow']['mae'] != result['comparison']['shadow']['mae']
