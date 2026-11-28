from datetime import date
import json

import numpy as np
import pandas as pd
import pytest

from nba_archived_simulation import SLOTS, _member_indices, score_range
from nba_simulation import candidate_range_receipt


def test_saved_player_set_cannot_shift_to_another_pool_row():
    pool = pd.DataFrame({'id':[f'137257-{i}' for i in range(9)]})
    original = dict(indices=list(range(9)), players=[dict(id=key,slot=slot) for key,slot in zip(pool.id,SLOTS)])
    assert _member_indices(original,pool) == list(range(9))
    with pytest.raises(ValueError,match='does not match'):
        _member_indices(original,pool.iloc[::-1].reset_index(drop=True))


def test_range_metrics_keep_missing_actuals_and_penalize_tail_misses():
    draws = np.arange(11)
    scored = score_range(draws,0)
    assert (scored['p10'],scored['p50'],scored['p90']) == (1,5,9)
    assert scored['below'] and not scored['covered'] and scored['interval_score']==18
    assert score_range(draws,9)['covered']
    assert score_range(draws,None)['interval_score'] is None


def test_receipt_preserves_exact_forecasts_and_disallows_partial_or_mismatched_ranges():
    projection = 23.538641342573829
    pool = pd.DataFrame(dict(fanduel_id=[f'137257-{i}' for i in range(9)],
                             adjusted_minutes=25.,adjusted_fd_points=projection))
    rosters = pool[['fanduel_id']].assign(lineup='A')
    ranges = pd.DataFrame([dict(lineup='A',reviewed_fd=projection*9,fd_p10=170.2,
                                fd_p50=210.8,fd_p90=248.7,fd_stddev=30.)])
    meta = dict(slate=date(2026,11,27),captured_at='2026-11-27T18:40:00-05:00',
                timing='before_scheduled_tip',draws=4000,seed=42,training_players=30)
    result = json.loads(candidate_range_receipt(pool,rosters,ranges,**meta))
    assert result['contest'] == '137257' and result['captured_at_utc'] == '2026-11-27T23:40:00+00:00'
    assert result['players'][0]['adjusted_fd_points'] == projection
    assert result['ranges'][0]['fd_p90']==248.7
    with pytest.raises(ValueError,match='distinct players'):
        candidate_range_receipt(pool,rosters.iloc[:-1],ranges,**meta)
    with pytest.raises(ValueError,match='projected totals'):
        candidate_range_receipt(pool,rosters,ranges.assign(reviewed_fd=42.),**meta)
    with pytest.raises(ValueError,match='timestamp'):
        candidate_range_receipt(pool,rosters,ranges,**dict(meta,captured_at='2026-11-28T18:40:00-05:00'))
