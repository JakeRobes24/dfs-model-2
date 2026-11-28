from datetime import date,timedelta
import pandas as pd
from nba_history_readiness import history_readiness
from nba_window_shadow import attach_window_inputs
from nba_pooled_history_shadow import attach_pooled_history
from test_nba_window_shadow import pool,logs

DAY=date(2026,11,28)

def test_attached_is_not_same_as_usable_and_stale_is_visible():
    base=pool()
    def result(history,p=base):
        f=attach_pooled_history(attach_window_inputs(p,history,DAY),history,DAY)
        before=f.copy(deep=True)
        out=history_readiness(f,DAY).iloc[0]
        pd.testing.assert_frame_equal(f,before)
        return out
    good=result(logs())
    assert good.history_eight_attached and good.history_eight_usable
    assert good.history_eight_recent_usable and good.history_pooled_usable
    bad=result([dict(r,assists=None) if i==7 else r for i,r in enumerate(logs())])
    assert bad.history_eight_attached and not bad.history_eight_usable
    assert bad.history_four_attached and not bad.history_pooled_usable
    stale=result([dict(r,game_date=r['game_date']-timedelta(days=6)) for r in logs()])
    assert stale.history_eight_usable and not stale.history_eight_recent_usable
    assert stale.history_eight_age_days==8
    assert not stale.history_pooled_usable
    q=result(logs(),base.assign(injury_flag='Q'))
    assert q.history_eight_attached and not q.history_eight_usable
    assert not q.history_pooled_usable


def test_eligible_coverage_and_duplicate_guard():
    import pytest
    f=attach_pooled_history(attach_window_inputs(pool(),logs(),DAY),logs(),DAY)
    assert history_readiness(f.assign(eligible=False),DAY).empty
    with pytest.raises(ValueError,match='Unique contest'):
        history_readiness(pd.concat([f,f]),DAY)
