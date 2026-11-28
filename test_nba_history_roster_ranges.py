from datetime import date,timedelta
import pandas as pd
import numpy as np
import pytest
from model import SLOTS
from nba_history_roster_ranges import simulate_archived_rosters,evaluate_archived_rosters

DAY=date(2026,11,27)
def fixture():
    history=[]
    for i in range(16):
        for p in range(25):
            history.append(dict(nba_id=str(p+1),team='BOS',game='BOS@NYK',
                source='https://www.nba.com/game/test/box-score',
                game_date=(date(2026,11,1)+timedelta(days=i)).isoformat(),
                minutes=22+(p+i)%12,points=12+(p+2*i)%15,reboundsTotal=5,
                assists=4,steals=1,blocks=0,turnovers=2,
                fieldGoalsAttempted=12+(p+i)%8,freeThrowsAttempted=4))
    ids=[f'137200-{i}' for i in range(10)]
    pool=pd.DataFrame(dict(fanduel_id=ids,eligible=True,salary=6000,
        team=['BOS','NYK','DAL']*3+['BOS'],
        roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL',
        adjusted_minutes=30,adjusted_fd_points=32))
    roster=pd.DataFrame([dict(lineup=k,slot=s,fanduel_id=p)
                        for k,players in [(1,ids[:9]),(2,ids[1:])] for s,p in zip(SLOTS,players)])
    actual=pd.DataFrame(dict(fanduel_id=ids,actual_minutes=30,actual_points=33,
        verified_outcome='played',nba_source='official'))
    return history,pool,roster,actual

def test_shared_draws_and_complete_legal_rosters():
    h,p,r,a=fixture()
    models,meta=simulate_archived_rosters(h,p,r,slate=DAY,draws=200)
    assert meta['training_latest']<'2026-11-27' and meta['players']==10
    assert not meta['certified']
    assert len(models)==2
    result=evaluate_archived_rosters(models,p,r,a)
    assert len(result['lineups'])==4 and len(result['pairs'])==2
    assert all(x['actual']==297 for x in result['lineups'])
    for model in models.values():
        totals=model._lineup_totals(r)
        assert np.allclose(totals[1]-totals[2],model.fd_points[:,0]-model.fd_points[:,-1])

def test_missing_and_short_outcomes_never_imputed():
    h,p,r,a=fixture()
    models,_=simulate_archived_rosters(h,p,r,slate=DAY,draws=200)
    a.loc[0,'actual_minutes']=5
    result=evaluate_archived_rosters(models,p,r,a)
    assert result['excluded_lineups']==['1']
    assert len(result['lineups'])==2 and not result['pairs']

def test_invalid_salary_and_slot_rejected():
    h,p,r,a=fixture()
    with pytest.raises(ValueError):simulate_archived_rosters(h,p.assign(salary=8000),r,slate=DAY)
    bad=r.copy()
    bad.loc[0,'slot']='UTIL'
    with pytest.raises(ValueError):simulate_archived_rosters(h,p,bad,slate=DAY)

def test_no_target_day_training():
    h,p,r,a=fixture()
    first,_=simulate_archived_rosters(h,p,r,slate=DAY,draws=200)
    h.append(dict(h[0],game_date=DAY,points=100))
    second,_=simulate_archived_rosters(h,p,r,slate=DAY,draws=200)
    for k in first:
        assert np.array_equal(first[k].fd_points,second[k].fd_points)


@pytest.mark.parametrize("teams", [["BOS", "NYK"] * 5, ["BOS"] * 5 + ["NYK"] * 3 + ["DAL"] * 2])
def test_illegal_team_composition_rejected(teams):
    history, pool, roster, _ = fixture()
    with pytest.raises(ValueError, match='violates contest rules'):
        simulate_archived_rosters(history, pool.assign(team=teams), roster, slate=DAY)
