import numpy as np
import pandas as pd
import pytest
from nba_simulation import OutcomeDraws
from nba_portfolio_stress import stress_portfolio


def test_stress_enumerates_equal_budget_portfolios_preserves_scores_and_is_deterministic():
    rng = np.random.default_rng(9)
    ids = pd.Index([f'p{i}' for i in range(16)])
    draws = OutcomeDraws(ids,np.full((4000,16),30.),rng.normal(30,8,(4000,16)))
    pool = pd.DataFrame(dict(fanduel_id=ids,team=['BOS','NYK','CLE','ORL']*4,
                             game=['BOS@NYK','BOS@NYK','CLE@ORL','CLE@ORL']*4))
    rosters = pd.DataFrame([dict(lineup=i+1,fanduel_id=p) for i in range(8) for p in ids[i:i+9]])
    ranges = pd.DataFrame(dict(lineup=range(1,9),reviewed_fd=[302,302,301,301,300,300,299,290]))
    before = ranges.copy(deep=True)
    selected, report = stress_portfolio(draws,pool,rosters,ranges)
    assert len(selected)==4 and len(set(selected))==4
    assert len(report)>1 and len(report)<=70
    assert report['Projection loss per entry'].le(2.00000001).all()
    assert report['Worst-scenario best P90'].is_monotonic_decreasing
    assert report['Worst-scenario best P90'].ge(report['Worst-scenario best P10']).all()
    assert report['Average shared players'].between(0,9).all()
    assert report.iloc[0]['Candidates']==tuple(selected)
    reverse,_ = stress_portfolio(draws,pool,rosters.iloc[::-1],ranges.iloc[::-1])
    assert reverse==selected
    pd.testing.assert_frame_equal(ranges,before)
    duplicate = pd.concat([rosters.iloc[:9].assign(lineup=i) for i in range(1,9)])
    with pytest.raises(ValueError,match='distinct'):
        stress_portfolio(draws,pool,duplicate,ranges)
