import pytest
from nba_team_allocation_audit import allocation_candidates, regulation_allocation_audit


def team():
    return [dict(date="2026-11-27", team="A", id=str(i), m=m,
                 p=m, am=m, ap=m)
            for i,m in enumerate([32,32,32,32,32,20,20,20,20])]


def test_fixed_hypotheses_conserve_regulation_minutes_without_outcomes():
    rows = team()
    forecasts = allocation_candidates(rows)
    assert forecasts == allocation_candidates([dict(r, am=None, ap=None) for r in rows])
    for policy in ("normalized","top_five_down","top_five_up"):
        assert sum(r["minutes"][policy] for r in forecasts.values()) == pytest.approx(240)
    assert sum(r["minutes"]["top_five_down"] for r in forecasts.values() if r["top_five"]) == pytest.approx(152)
    assert sum(r["minutes"]["top_five_up"] for r in forecasts.values() if r["top_five"]) == pytest.approx(168)


def test_audit_keeps_common_rows_and_excludes_incomplete_team():
    rows = team()
    result = regulation_allocation_audit(rows)
    assert result["teams"][0]["scored"]
    assert result["dates"]["2026-11-27"]["fd"]["raw"]["mae"] == 0
    assert result["dates"]["2026-11-27"]["fd"]["top_five_down"]["n"] == 9
    rows[0]["am"] = None
    assert not regulation_allocation_audit(rows)["teams"][0]["scored"]
    rows[0]["m"] = None
    assert allocation_candidates(rows) is None


def test_reject_duplicate_and_infeasible_minute_transfer():
    rows = team()
    with pytest.raises(ValueError, match="unique"):
        regulation_allocation_audit(rows+[rows[0]])
    rows[0]["m"] = 48
    # A 48-minute raw estimate is allowed, but missing rows are not.
    rows[1]["m"] = -1
    assert allocation_candidates(rows) is None
    assert allocation_candidates([dict(id=str(i), m=48 if i<5 else 1)
                                  for i in range(6)]) is None


def test_missing_points_not_imputed_even_when_team_minutes_reconcile():
    rows = team()
    rows[0]["ap"] = None
    result = regulation_allocation_audit(rows)
    assert result["teams"][0]["scored"]
    assert result["dates"]["2026-11-27"]["fd"]["raw"]["n"] == 8
