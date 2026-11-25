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


def test_frozen_pool_to_optimized_candidates_to_simulation():
    from nba_candidate_experiment import build_experiment
    from slate_replay_capture import capture_pool
    day = date(2026,11,25)
    ids = [f'143-{i}' for i in range(24)]
    teams = ['BOS','NYK','CLE','ORL'] * 6
    pool = pd.DataFrame({'fanduel_id':ids, 'fanduel_name':ids, 'salary':6000,
        'team':teams, 'game':['BOS@NYK' if t in ('BOS','NYK') else 'CLE@ORL' for t in teams],
        'roster_eligibility':'PG/SG/SF/PF/C/G/F/F/C/UTIL', 'eligible':True,
        'prelock_status':'', 'prelock_starter':'', 'confidence':'high',
        'minutes_method':'DAILY', 'injury_flag':'', 'projected_minutes':30,
        'projected_fd_points':list(range(20,44)), 'adjusted_minutes':30,
        'adjusted_fd_points':list(range(21,45))})
    schedule = [dict(awayTeam={'teamTricode':a},homeTeam={'teamTricode':b},
                     gameTimeUtc='2026-11-25T23:00:00Z') for a,b in [('BOS','NYK'),('CLE','ORL')]]
    frozen = capture_pool(pool,pd.DataFrame(),schedule,day,'2026-11-25T20:00:00Z',('a'*64,'b'*64))
    training = pd.DataFrame({'slate_date':'2026-11-24','fanduel_id':[f'142-{i}' for i in range(24)],
        'eligible':True,'daily_minutes':30,'daily_points':30,'actual_minutes':30,
        'actual_points':[28,32]*12,'verified_outcome':'played','nba_source':'NBA box',
        'replay_before_full_slate_tip':True,'replay_captured_at_utc':'2026-11-24T20:00:00Z',
        'replay_cutoff_utc':'2026-11-24T23:00:00Z'})
    rosters,ranges,selections,count = build_experiment(frozen,training,day)
    assert rosters.lineup.nunique()==8
    assert count==24 and len(ranges)==8
    assert all(len(labels)==4 for labels in selections.values())
    expected = rosters.groupby('lineup').adjusted_fd_points.sum()
    assert ranges.set_index('lineup').reviewed_fd.to_dict()==expected.to_dict()
    assert rosters.groupby('lineup').fanduel_id.nunique().eq(9).all()
    with pytest.raises(ValueError,match='Insufficient earlier'):
        build_experiment(frozen,training.assign(slate_date='2026-11-25'),day)


def test_stress_policy_scores_against_same_actuals_with_own_declaration():
    from nba_portfolio_stress import STRESS_POLICY
    ids = [f'143-{i}' for i in range(16)]
    pool = pd.DataFrame({'fanduel_id':ids,'salary':6000,
        'roster_eligibility':'PG/SG/SF/PF/C/G/F/F/C/UTIL',
        'team':['BOS','NYK','CLE','ORL']*4})
    rosters = pd.DataFrame([dict(lineup=i+1,slot=s,fanduel_id=p)
        for i in range(8) for s,p in zip(SLOTS,ids[i:i+9])])
    selections = {'Projection ranked':[1,2,3,4],'Simulated P90 ranked':[5,6,7,8],
                  STRESS_POLICY:[1,3,5,7]}
    actual = pd.DataFrame(dict(fanduel_id=ids,outcome='Played',nba_fd_points=30,nba_source='NBA box'))
    report,_ = score_experiment(pool,rosters,selections,actual,date(2026,11,25))
    assert report.set_index('Policy').loc[STRESS_POLICY,'Period']=='Exploratory'
    assert report.Entries.eq(4).all()
    assert report['Best actual FD'].eq(270).all()
