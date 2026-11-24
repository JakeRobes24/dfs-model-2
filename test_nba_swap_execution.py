"""Regression tests for executable, identity-safe direct swap paths."""
import pandas as pd
import pytest
from model import SLOTS
from nba_swap_execution import plan_direct_swaps

def fixture():
    rows = [{"fanduel_id": str(i), "fanduel_name": "Player "+str(i),
             "team": "CHA", "salary": 6500, "eligible": True,
             "roster_eligibility": s} for i,s in enumerate(SLOTS)]
    rows[1]["salary"] = 7500
    rows[6]["salary"] = 6500
    rows[8]["salary"] = 6000
    rows[8]["roster_eligibility"] = "SG/UTIL"
    rows += [
        dict(rows[6], fanduel_id="reid", fanduel_name="Naz Reid", salary=6200),
        dict(rows[8], fanduel_id="quickley", fanduel_name="Immanuel Quickley",
             roster_eligibility="PG/G/F/UTIL", salary=6300),
        dict(rows[5], fanduel_id="new", salary=6800),
        dict(rows[2], fanduel_id="miller", fanduel_name="Brandon Miller", team="CHA"),
        dict(rows[2], fanduel_id="baba", fanduel_name="Baba Miller", team="LAC"),
    ]
    return pd.DataFrame(rows), tuple(str(i) for i in range(9))

def test_savings_and_move_order():
    p,b = fixture()
    # A $60k entry: cheap forward before replacing utility, then move original
    # utility player into SG. Quickley is not SG eligible.
    p.loc[p.fanduel_id.eq("0"), "salary"] += 1000
    a=list(b);a[6]="reid";a[8]="quickley";a[1]="8"
    steps=plan_direct_swaps(p,b,a)
    assert [s["slot"] for s in steps] == ["F/C","UTIL 2","SG"]
    assert all(s["remaining_salary"] >= 0 for s in steps)

def test_locked_move_rejected():
    p,b=fixture();a=list(b);a[8]="quickley";a[1]="8"
    with pytest.raises(ValueError, match="closed"):
        plan_direct_swaps(p,b,a,{"8"})

def test_wrong_position_rejected():
    p,b=fixture();a=list(b);a[1]="quickley"
    with pytest.raises(ValueError, match="Invalid"):
        plan_direct_swaps(p,b,a)

def test_distinct_identity():
    p,b=fixture();a=list(b);a[2]="miller"
    s=plan_direct_swaps(p,b,a)[0]
    assert (s["in_id"],s["in_player"],s["in_team"])==("miller","Brandon Miller","CHA")

def test_unavailable_replacement():
    p,b=fixture();a=list(b);a[2]="miller"
    p.loc[p.fanduel_id.eq("miller"),"eligible"]=False
    with pytest.raises(ValueError, match="not eligible"):
        plan_direct_swaps(p,b,a)

def test_utility_cycle_not_directly_executable():
    p,b=fixture();a=list(b);a[7],a[8]=a[8],a[7]
    assert plan_direct_swaps(p,b,a) is None

def test_duplicate_rejected():
    p,b=fixture();a=list(b);a[7]=a[8]
    with pytest.raises(ValueError, match="Invalid"):
        plan_direct_swaps(p,b,a)

def test_unchanged_locked_roster():
    p,b=fixture()
    assert plan_direct_swaps(p,b,b,set(b))==[]


def test_alternative_layout_preserves_existing_slots():
    from nba_swap_execution import find_executable_layout
    p,b=fixture();a=list(b);a[7],a[8]=a[8],a[7]
    layout,steps=find_executable_layout(p,b,a)
    assert tuple(layout)==b
    assert steps==[]

def test_alternative_layout_keeps_same_players_and_minimizes_moves():
    from nba_swap_execution import find_executable_layout
    p,b=fixture()
    p.loc[p.fanduel_id.eq("1"),"roster_eligibility"]="SG/UTIL"
    a=list(b);a[1]="8";a[8]="quickley"
    # Quickley is only UTIL eligible, so no direct one-step replacement
    # of SG player can attain the same roster. The two-step sequence is valid.
    layout,steps=find_executable_layout(p,b,a)
    assert set(layout)==set(a)
    assert [s["slot"] for s in steps]==["UTIL 2","SG"]


@pytest.mark.parametrize("salary",[6500.5,-1,float("nan"),float("inf")])
def test_invalid_salary_rejected(salary):
    p,b=fixture()
    p["salary"]=p.salary.astype(float)
    p.loc[p.fanduel_id.eq("0"),"salary"]=salary
    with pytest.raises(ValueError,match="Invalid contest salary"):
        plan_direct_swaps(p,b,b)


def test_retained_open_ineligible_player_rejected():
    p,b=fixture()
    p.loc[p.fanduel_id.eq("0"),"eligible"]=False
    with pytest.raises(ValueError,match="retained open"):
        plan_direct_swaps(p,b,b)
    assert plan_direct_swaps(p,b,b,{"0"})==[]
