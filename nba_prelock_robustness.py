"""Pre-lock ranking robustness for frozen NBA lineup candidates.

Scenario analysis only: no optimizer, independent source validation, or late-news certification.
"""
import csv
import io
import math


def compare_minutes_bounds(pool_csv, lineup_csv, player_id, low_minutes, high_minutes):
    pool_rows = list(csv.DictReader(io.StringIO(pool_csv)))
    pool = {}
    for row in pool_rows:
        pid = row.get("id", "").strip()
        if not pid or pid in pool:
            raise ValueError("Missing or duplicate contest player ID")
        pool[pid] = row
    if player_id not in pool:
        raise ValueError("Target player missing from pool")
    player = pool[player_id]
    baseline_minutes = float(player["consensus_scenario_minutes"])
    baseline_fd = float(player["consensus_scenario_fd"])
    bounds = (float(low_minutes), float(high_minutes))
    if (not all(math.isfinite(v) for v in (baseline_minutes, baseline_fd, *bounds))
            or baseline_minutes <= 0 or baseline_fd < 0
            or bounds[0] <= 0 or bounds[1] < bounds[0]):
        raise ValueError("Invalid baseline or minute bounds")

    groups = {}
    for row in csv.DictReader(io.StringIO(lineup_csv)):
        groups.setdefault(row["lineup"], []).append(row)
    if not groups:
        raise ValueError("No lineups")
    baselines = {}
    exposure = {}
    for label, rows in groups.items():
        ids = [r["player_id"] for r in rows]
        if len(ids) != 9 or len(set(ids)) != 9:
            raise ValueError("Each candidate must contain nine unique IDs")
        if any(pid not in pool for pid in ids):
            raise ValueError("Lineup player not found in frozen pool")
        total = 0.0
        for row in rows:
            score = float(row["scenario_fd"])
            pool_score = float(pool[row["player_id"]]["consensus_scenario_fd"])
            if not math.isfinite(score) or abs(score-pool_score) > 1e-6:
                raise ValueError("Frozen lineup projection mismatch")
            total += score
        baselines[label] = total
        exposure[label] = int(player_id in ids)
    def totals_at(minutes):
        delta = baseline_fd * (minutes / baseline_minutes - 1)
        return {name: round(total + exposure[name]*delta, 3)
                for name, total in baselines.items()}
    scenarios = []
    for minutes in bounds:
        totals = totals_at(minutes)
        winner = sorted(totals, key=lambda name: (-totals[name], name))[0]
        scenarios.append({"minutes": minutes, "totals": totals, "winner": winner})
    crossings = []
    labels = sorted(groups)
    for i, a in enumerate(labels):
        for b in labels[i+1:]:
            if exposure[a] == exposure[b]:
                continue
            slope = (exposure[a] - exposure[b]) * baseline_fd / baseline_minutes
            crossing = baseline_minutes - (baselines[a]-baselines[b]) / slope
            if bounds[0] <= crossing <= bounds[1]:
                crossings.append({"lineups": [a,b], "minutes": round(crossing,4)})
    return {"player_id":player_id,"baseline_minutes":baseline_minutes,
            "bounds":scenarios,"crossings":crossings,
            "winner_changes":scenarios[0]["winner"] != scenarios[1]["winner"],
            "method":"linear per-minute sensitivity; frozen candidate set; not a projection update"}
