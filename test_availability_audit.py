import pytest
from availability_audit import availability_audit


def row(id, outcome, actual, daily, reviewed, status=""):
    return dict(sport="NBA", date="2026-11-27", contest="137257", id=id,
                outcome=outcome, actual=actual, daily=daily, reviewed=reviewed, status=status)


def test_strict_common_sample_and_unknown_exposure():
    rows = [row("1","played",10,8,12), row("2","confirmed_nonplay",0,20,0,"O"),
            row("3","unknown",0,30,15), row("4","played",5,None,5),
            row("5","team",10,10,10)]
    r = next(iter(availability_audit(rows,["daily","reviewed"]).values()))
    assert r["paired"]["both"]["daily"]["n"] == 2
    assert r["paired"]["both"]["daily"]["mae"] == 11
    assert r["paired"]["both"]["reviewed"]["mae"] == 1
    assert r["exposure"]["daily"]["unknown_positive_sum"] == 30
    assert r["exposure"]["reviewed"]["nonplay_positive"] == 0
    assert r["by_status"]["O"]["confirmed_nonplay"] == 1


def test_zero_forecast_and_zero_point_played_are_distinct_from_nonplay():
    rows = [row("1","played",0,0,0), row("2","played",5,0,0)]
    r = next(iter(availability_audit(rows,["daily","reviewed"]).values()))
    assert r["exposure"]["daily"]["played_zero"] == ["1","2"]
    assert r["paired"]["confirmed_nonplay"]["daily"]["n"] == 0


def test_reject_bad_labels_duplicate_keys_and_nonzero_dnp():
    for rows in ([row("1","missing",None,1,1)],
                 [row("1","confirmed_nonplay",4,1,1)],
                 [row("1","played",1,1,1), row("1","played",1,1,1)]):
        with pytest.raises(ValueError):
            availability_audit(rows,["daily"])
