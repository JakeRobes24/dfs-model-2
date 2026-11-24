from datetime import date
import pandas as pd
import pytest

from model import SLOTS
from nba_candidate_experiment import select_portfolios, score_experiment


def test_fixed_candidate_rankings_and_paired_actuals():
    ids = [f'143-{i}' for i in range(16)]
    pool = pd.DataFrame({'fanduel_id': ids, 'salary': 6000,
                         'roster_eligibility': 'PG/SG/SF/PF/C/G/F/F/C/UTIL',
                         'team': ['BOS','NYK','CLE','ORL']*4})
    rosters = pd.DataFrame([
        {'lineup': i+1, 'slot': slot, 'fanduel_id': pid}
        for i in range(8) for slot,pid in zip(SLOTS,ids[i:i+9])
    ])
    ranges = pd.DataFrame({'lineup': list(range(1,9)), 'reviewed_fd': list(range(308,300,-1)),
                           'fd_p90': list(range(350,358))})
    selections = select_portfolios(ranges)
    assert selections['Projection ranked'] == [1,2,3,4]
    assert selections['Simulated P90 ranked'] == [8,7,6,5]
    results = pd.DataFrame({'fanduel_id': ids, 'outcome': 'Played',
                            'nba_fd_points': list(range(20,36)), 'nba_source': 'NBA official box'})
    report, totals = score_experiment(pool,rosters,selections,results,date(2026,11,25))
    assert report.Period.eq('Prospective').all()
    assert report.Entries.eq(4).all()
    assert report.iloc[0]['Best actual FD'] == 243
    assert report.iloc[1]['Best actual FD'] == 279
    assert len(totals)==8
    with pytest.raises(ValueError, match='unresolved'):
        score_experiment(pool,rosters,selections,results.assign(nba_source=''),date(2026,11,25))
    results.loc[0,'outcome'] = 'Did not play'
    results.loc[0,'nba_fd_points'] = None
    _, totals = score_experiment(pool,rosters,selections,results,date(2026,11,24))
    assert totals.iloc[0].actual_fd == 196


def test_selection_rejects_missing_forecasts_and_is_order_invariant():
    frame = pd.DataFrame({'lineup': list(range(1,9)), 'reviewed_fd': 300, 'fd_p90': 350})
    assert select_portfolios(frame) == select_portfolios(frame.iloc[::-1])
    with pytest.raises(ValueError, match='finite'):
        select_portfolios(frame.assign(fd_p90=None))
    with pytest.raises(ValueError, match='unique'):
        select_portfolios(pd.concat([frame,frame]))
