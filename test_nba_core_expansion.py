from datetime import date
import pandas as pd
import pytest
from model import optimize
from nba_core_expansion import build_core_expansion,score_core_expansion,CORE_CONTROL,CORE_EXPANDED


def test_core_expansion_uses_common_draws_and_original_reference():
    ids=[f'143-{i:02d}' for i in range(24)]
    pool=pd.DataFrame(dict(fanduel_id=ids,fanduel_name=ids,salary=6000,
        team=['BOS','NYK','CLE','ORL']*6,game=['BOS@NYK','BOS@NYK','CLE@ORL','CLE@ORL']*6,
        roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL',eligible=True,
        confidence='high',minutes_method='DAILY',injury_flag='',adjusted_minutes=30,
        adjusted_fd_points=list(range(20,44))))
    baseline=optimize(pool,number=8,max_overlap=7)
    history=pd.DataFrame(dict(slate_date='2026-11-24',fanduel_id=[f'142-{i}' for i in range(24)],
        eligible=True,daily_minutes=30,daily_points=30,actual_minutes=30,
        actual_points=[28,32]*12,verified_outcome='played',nba_source='NBA box',
        replay_before_full_slate_tip=True,replay_captured_at_utc='2026-11-24T20:00:00Z',
        replay_cutoff_utc='2026-11-24T23:00:00Z'))
    original=baseline.copy(deep=True)
    union,chosen,metrics=build_core_expansion(pool,history,date(2026,11,25),baseline,
                                             time_budget_seconds=30)
    assert 8<=union.lineup.nunique()<=12
    assert len(chosen[CORE_CONTROL])==len(chosen[CORE_EXPANDED])==4
    assert set(chosen[CORE_CONTROL])<=set(baseline.lineup)
    assert metrics['Simulated best P90 change']>=-1e-8
    assert metrics['New core candidates']==union.lineup.nunique()-8
    pd.testing.assert_frame_equal(baseline,original)
    actual=pd.DataFrame(dict(fanduel_id=ids,outcome='Played',nba_fd_points=30,nba_source='NBA box'))
    report=score_core_expansion(pool,union,chosen,actual,date(2026,11,25))
    assert report.Period.eq('Exploratory').all()
    assert report['Best actual FD'].eq(270).all()
    assert score_core_expansion(pool,union,chosen,actual,date(2026,11,26)).Period.eq('Prospective').all()


def test_incomplete_core_search_does_not_become_a_paired_result(monkeypatch):
    ids=[f'143-{i:02d}' for i in range(24)]
    pool=pd.DataFrame(dict(fanduel_id=ids,fanduel_name=ids,salary=6000,
        team=['BOS','NYK','CLE','ORL']*6,game=['BOS@NYK','BOS@NYK','CLE@ORL','CLE@ORL']*6,
        roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL',eligible=True,
        confidence='high',minutes_method='DAILY',injury_flag='',adjusted_minutes=30,
        adjusted_fd_points=list(range(20,44))))
    baseline=optimize(pool,number=8,max_overlap=7)
    monkeypatch.setattr('nba_core_expansion.challenge_shared_core',lambda *a,**kw:
        (pd.DataFrame({'Status':['Candidate not certified optimal']}),pd.DataFrame()))
    with pytest.raises(ValueError,match='incomplete'):
        build_core_expansion(pool,pd.DataFrame(),date(2026,11,25),baseline)
