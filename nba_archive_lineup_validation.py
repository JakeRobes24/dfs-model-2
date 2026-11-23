"""Validate archived NBA lineup rows against exact contest-scoped scenario IDs."""
import csv
import io
from collections import defaultdict
from math import isfinite

SLOTS = ('PG', 'SG', 'SF', 'PF', 'C', 'G/F', 'F/C', 'UTIL', 'UTIL')

def validate_archived_lineups(pool_csv, lineup_csv, *, salary_cap=60000):
    pool = list(csv.DictReader(io.StringIO(pool_csv)))
    rosters = list(csv.DictReader(io.StringIO(lineup_csv)))
    if not pool or not rosters:
        raise ValueError("Pool and lineups are required")
    lookup = {}
    for p in pool:
        pid = p["id"].strip()
        if not pid or pid in lookup:
            raise ValueError("Duplicate or empty pool player ID")
        lookup[pid] = p
    grouped = defaultdict(list)
    for r in rosters:
        grouped[r["lineup"]].append(r)
    report = []
    for name, rows in sorted(grouped.items(), key=lambda x: int(x[0])):
        if len(rows) != 9 or len({r["player_id"] for r in rows}) != 9:
            raise ValueError(f"Lineup {name}: must have nine unique players")
        if sorted(r["slot"] for r in rows) != sorted(SLOTS):
            raise ValueError(f"Lineup {name}: invalid slots")
        salary = 0
        projection = 0
        for r in rows:
            p = lookup.get(r["player_id"])
            if p is None:
                raise ValueError(f"Lineup {name}: missing contest ID")
            if p["player"] != r["player"] or int(p["salary"]) != int(r["salary"]):
                raise ValueError(f"Lineup {name}: player/salary mismatch")
            # Source positions are encoded as PG/G/F/UTIL or PF/G/F/F/C/UTIL.
            eligibility = "/" + p["positions"].strip("/") + "/"
            slot = r["slot"]
            if slot != "UTIL" and ("/" + slot + "/") not in eligibility:
                raise ValueError(f"Lineup {name}: ineligible slot")
            if p["status"].strip().upper() in {"O", "OUT", "INACTIVE", "IR"}:
                raise ValueError(f"Lineup {name}: out player")
            value = float(r["scenario_fd"])
            pool_value = float(p["consensus_scenario_fd"])
            if not isfinite(value) or not isfinite(pool_value) or abs(value - pool_value) > 0.000001:
                raise ValueError(f"Lineup {name}: scenario projection mismatch")
            salary += int(r["salary"])
            projection += value
        if salary > salary_cap:
            raise ValueError(f"Lineup {name}: exceeds salary cap")
        report.append({"lineup": name, "players": 9, "salary": salary,
                       "scenario_fd": round(projection, 3),
                       "valid_against_archived_pool": True})
    return {"contest_player_count": len(pool), "lineups": report,
            "scope": "archived scenario legality only; not independently certified final prelock"}
