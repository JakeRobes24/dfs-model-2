import pytest

from paired_component_audit import (
    nba_component_diagnostic, nfl_component_pairs, yardage_attribution,
)


def test_nba_fixed_component_substitutions_on_identical_rows():
    row = dict(date="2026-11-27", id="137257-1", m=20, p=30,
               sm=30, sp=36, am=25, ap=30)
    result = nba_component_diagnostic([row, dict(row, id="137257-2", am=0)])
    day = result["dates"]["2026-11-27"]
    assert result["excluded"] == 1
    assert all(x["n"] == 1 for x in day["fd"].values())
    assert day["fd"]["reviewed"]["mae"] == 0
    assert day["fd"]["source"]["bias"] == 6
    assert day["fd"]["source_minutes_only"]["bias"] == 15
    assert day["fd"]["source_rate_only"]["bias"] == -6
    assert day["fd"]["half_both"]["bias"] == pytest.approx(3.75)
    assert day["disagreement"][2]["reviewed"]["n"] == 1
    assert day["disagreement"][0]["source"]["mae"] is None


def test_duplicate_archive_id_fails_closed():
    row = dict(date="2026-11-27", id="137257-1")
    with pytest.raises(ValueError, match="unique"):
        nba_component_diagnostic([row, row])


def test_nfl_uses_explicit_passing_tuple_indexes_and_does_not_invent_targets():
    forecast = dict(pass_attempts=30, passing_yards=220, passing_td=1.5,
                    interceptions=.7, receptions=4, receiving_yards=30, receiving_td=.2,
                    rushing_attempts=1)
    actual = dict(pass_ignored=True, **{"pass": [21, 10, 81, 0, 2]},
                  receive=[5, 3, 25, 0])
    pairs = nfl_component_pairs(forecast, actual)
    assert pairs["passing_yards"] == (220, 81)
    assert pairs["passing_td"] == (1.5, 0)
    assert pairs["interceptions"] == (.7, 2)
    assert pairs["receptions"] == (4, 3)
    assert "targets" not in pairs and "rushing_attempts" not in pairs
    with pytest.raises(ValueError, match="shape"):
        nfl_component_pairs(forecast, {"pass": [21, 81, 0, 2]})


def test_nfl_yardage_attribution_is_exact_and_zero_volume_is_missing():
    d = yardage_attribution(16.8, 32, 94.5, 117, .1)
    assert d["volume"] + d["rate"] == pytest.approx((94.5-117)*.1)
    assert d["volume"] == pytest.approx(-7.05375)
    assert yardage_attribution(1, 0, 4, 0, .1) is None
