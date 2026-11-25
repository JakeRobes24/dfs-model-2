"""Regression for the team-limit defect observed in the hosted Nov23 test."""
import pandas as pd
import pytest
from model import optimize, SLOTS
from nba_classic_rules import validate_team_roster
from nba_swap_execution import plan_direct_swaps
from lineup_challenger import challenge_lineups
from test_nba_optimizer_integration import fixture_pool

def test_team_cap_is_part_of_optimization():
    pool=fixture_pool()
    pool['team']=['HOU']*12+['BOS']*8+['NYK']*8+['TOR']*8
    result=optimize(pool,number=4)
    assert result.lineup.nunique()==4
    for _,roster in result.groupby('lineup'):
        assert validate_team_roster(pool,roster.fanduel_id,require_teams=True)
        assert roster.team_rules_verified.all()
        assert len(roster)==9 and roster.salary.sum()<=60000
    best=result.loc[result.lineup.eq(1)]
    assert sum(pool.set_index('fanduel_id').loc[best.fanduel_id,'team'].eq('HOU'))==4

def test_two_teams_cannot_fill_nine_slots():
    pool=fixture_pool()
    pool['team']=['HOU']*18+['BOS']*18
    assert optimize(pool,number=1).empty

def test_missing_or_invalid_contest_team_fails_closed():
    pool=fixture_pool()
    for team in ('',None,'not-a-team'):
        broken=pool.copy()
        broken.loc[0,'team']=team
        with pytest.raises(ValueError,match='team codes'):
            optimize(broken,number=1)
    with pytest.raises(ValueError,match='authoritative teams'):
        optimize(pool.drop(columns='team').assign(import_issue=''),number=1)

def test_aliases_cannot_evade_team_cap():
    pool=fixture_pool()
    pool['team']=['HOU','Houston Rockets']*6+['BOS']*8+['NYK']*8+['TOR']*8
    roster=optimize(pool,number=1)
    assert validate_team_roster(pool,roster.fanduel_id,require_teams=True)

def test_challenger_reports_illegal_team_composition():
    pool=fixture_pool()
    pool['team']=['HOU']*12+['BOS']*8+['NYK']*8+['TOR']*8
    bad=pd.DataFrame({'lineup':1,'slot':SLOTS,'fanduel_id':pool.fanduel_id.iloc[:9].tolist()})
    _,summary,alternatives=challenge_lineups(pool,bad)
    assert 'Invalid team composition' in summary.iloc[0].issues
    assert validate_team_roster(pool,alternatives.fanduel_id,require_teams=True)

def test_intermediate_team_cap_controls_swap_order():
    pool=fixture_pool().iloc[:11].copy()
    pool['team']=['HOU']*4+['BOS']*3+['NYK']*2+['HOU','BOS']
    before=tuple(pool.fanduel_id.iloc[:9])
    after=list(before)
    after[4]=pool.fanduel_id.iloc[9]
    after[0]=pool.fanduel_id.iloc[10]
    # Cheap HOU addition would normally come first, but would make five HOU.
    pool.loc[9,'salary']=5500
    pool.loc[10,'salary']=6500
    steps=plan_direct_swaps(pool,before,after)
    assert [x['out_id'] for x in steps]==[before[0],before[4]]
    bad=list(before);bad[4]=pool.fanduel_id.iloc[9]
    with pytest.raises(ValueError,match='team composition'):
        plan_direct_swaps(pool,before,bad)

def test_locked_team_counts_are_included():
    pool=fixture_pool()
    pool['team']=['HOU']*12+['BOS']*8+['NYK']*8+['TOR']*8
    fixed={i:pool.fanduel_id.iloc[i] for i in range(4)}
    result=optimize(pool,number=1,fixed_slots=fixed,closed_players=set(fixed.values()))
    assert validate_team_roster(pool,result.fanduel_id,require_teams=True)
    assert set(fixed.values())<=set(result.fanduel_id)
    fixed[4]=pool.fanduel_id.iloc[4]
    assert optimize(pool,number=1,fixed_slots=fixed,closed_players=set(fixed.values())).empty
