"""Validate a historical NFL FanDuel lineup fixture without inventing missing projections."""
import json
import math
import sys
from collections import Counter
from pathlib import Path

EXPECTED = Counter({"QB": 1, "RB": 2, "WR": 3, "TE": 1, "FLEX": 1, "DEF": 1})


def validate(data):
    errors, warnings = [], []
    rows = data.get("lineup", [])
    if len(rows) != 9:
        errors.append("Exactly nine players required")
    if Counter(r.get("slot") for r in rows) != EXPECTED:
        errors.append("Incorrect roster slot composition")
    names = [r.get("player") for r in rows]
    if len(names) != len(set(names)):
        errors.append("Duplicate player")
    salaries = [r.get("salary") for r in rows]
    if any(type(x) is not int or x < 0 for x in salaries):
        errors.append("Invalid salary")
    salary_total = sum(x for x in salaries if type(x) is int)
    if salary_total > data.get("salary_cap", 0):
        errors.append("Salary cap exceeded")
    actuals = [r.get("actual_fd") for r in rows]
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in actuals):
        errors.append("Invalid actual score")
    actual_total = sum(x for x in actuals if type(x) in (int, float) and math.isfinite(x))
    if abs(actual_total - data.get("actual_total_fd", 0)) > .01:
        errors.append("Actual total mismatch")
    known = [r for r in rows if r.get("prelock_fd") is not None]
    missing = [r for r in rows if r.get("prelock_fd") is None]
    if any(type(r["prelock_fd"]) not in (int, float) or not math.isfinite(r["prelock_fd"]) for r in known):
        errors.append("Invalid known projection")
    if len(known) != data.get("recovered_projection_count"):
        errors.append("Recovered projection count mismatch")
    if len(missing) != data.get("missing_individual_projection_count"):
        errors.append("Missing projection count mismatch")
    known_projection = sum(r["prelock_fd"] for r in known if type(r["prelock_fd"]) in (int, float) and math.isfinite(r["prelock_fd"]))
    known_actual = sum(r["actual_fd"] for r in known if type(r.get("actual_fd")) in (int, float) and math.isfinite(r["actual_fd"]))
    checks = [
        (known_projection, data.get("known_projected_subtotal", 0), "Known projection subtotal mismatch"),
        (known_actual, data.get("known_actual_subtotal", 0), "Known actual subtotal mismatch"),
        (data.get("projected_total_fd", 0) - known_projection, data.get("remaining_projected_subtotal", 0), "Remaining projected subtotal mismatch"),
        (actual_total - known_actual, data.get("remaining_actual_subtotal", 0), "Remaining actual subtotal mismatch"),
        (actual_total - data.get("projected_total_fd", 0), data.get("difference_total_fd", 0), "Projection difference mismatch"),
    ]
    for left, right, message in checks:
        if abs(left - right) > .01:
            errors.append(message)
    if missing:
        warnings.append(f"Individual projection accuracy cannot be computed for {len(missing)} players")
    warnings.extend([
        "Exact-slate eligibility cannot be independently certified without original contest CSV",
        "Pre-lock alternatives cannot be ranked without archived player pool and projections",
        "Preliminary total is not a certified final pre-lock projection",
    ])
    return {
        "passed": not errors, "errors": errors, "warnings": warnings,
        "salary_total": salary_total, "actual_total": round(actual_total, 2),
        "known_projection_count": len(known), "missing_projection_count": len(missing),
        "known_projection_subtotal": round(known_projection, 2),
        "known_actual_subtotal": round(known_actual, 2),
        "projection_delta": round(actual_total - data["projected_total_fd"], 2),
    }


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "tests/fixtures/nov22_2026_nfl_fd_preliminary.json"
    result = validate(json.loads(path.read_text()))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
