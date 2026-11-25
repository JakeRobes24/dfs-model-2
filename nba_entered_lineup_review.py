"""Compare observed entered NBA lineups against an archived scenario without hindsight optimization."""
import csv
from collections import Counter


def review_entered_lineups(scenario_csv, entries):
    rows = list(csv.DictReader(scenario_csv.splitlines()))
    names = [r.get("player", "").strip() for r in rows]
    if not rows or any(not n for n in names) or len(names) != len(set(names)):
        raise ValueError("Scenario must contain unique, nonempty player names")
    lookup = dict(zip(names, rows))
    reviewed = []
    for entry in entries:
        slots = entry["slots"]
        actuals = entry["actual_fd"]
        if len(slots) != 9 or len(set(slots.values())) != 9 or set(actuals) != set(slots.values()):
            raise ValueError("Each entered lineup needs nine unique players and nine actual scores")
        if any(n not in lookup for n in slots.values()):
            raise ValueError("Entered player missing from scenario; cannot certify comparison")
        salary = sum(int(lookup[n]["salary"]) for n in slots.values())
        if salary > 60000:
            raise ValueError("Lineup exceeds FanDuel salary cap")
        def total(field):
            return round(sum(float(lookup[n][field]) for n in slots.values()), 3)
        reviewed.append({"label": entry["label"], "salary": salary,
                         "daily_fd": total("daily_fd"),
                         "scenario_fd": total("consensus_scenario_fd"),
                         "actual_fd": round(sum(float(x) for x in actuals.values()), 3),
                         "players": sorted(slots.values())})
    return {"lineups": reviewed,
            "shared_players": sorted(set(reviewed[0]["players"]) & set(reviewed[1]["players"]))
            if len(reviewed) == 2 else [],
            "scope": "scenario-only; no final-prelock certification or full-pool actuals"}
