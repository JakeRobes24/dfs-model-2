"""Compare two timestamped pre-lock NFL candidate snapshots without hindsight.

This utility deliberately refuses comparisons with unknown individual projections
or mismatched contest identity. Actual results are never read by the scorer.
"""
from collections import Counter
from datetime import datetime, timezone


def _parse_time(value):
    if not isinstance(value, str) or not value:
        raise ValueError("A prelock timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO 8601 prelock timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("Prelock timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def validate_snapshot(snapshot):
    for field in ("contest_id", "slate_date", "source_version", "cutoff_utc"):
        if not snapshot.get(field):
            raise ValueError(f"Missing {field}")
    cutoff = _parse_time(snapshot["cutoff_utc"])
    players = snapshot.get("players")
    if not isinstance(players, list) or not players:
        raise ValueError("Full contest pool must be supplied")
    ids = [p.get("player_id") for p in players]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("Every pool player needs a unique player_id")
    for p in players:
        if not isinstance(p.get("salary"), int) or p["salary"] < 0:
            raise ValueError("Invalid salary")
        if not isinstance(p.get("positions"), list) or not p["positions"]:
            raise ValueError("Missing eligibility")
        if p.get("projection_fd") is None:
            raise ValueError("Missing individual player projection")
        if type(p["projection_fd"]) not in (int, float):
            raise ValueError("Invalid projection")
        import math
        if not math.isfinite(p["projection_fd"]):
            raise ValueError("Nonfinite projection")
        if _parse_time(p.get("asof_utc")) > cutoff:
            raise ValueError("Post-cutoff player projection")
    return {p["player_id"]: p for p in players}


def compare_prelock_candidates(snapshot, candidates):
    pool = validate_snapshot(snapshot)
    if not candidates:
        raise ValueError("At least one candidate required")
    results = []
    for candidate in candidates:
        if candidate.get("contest_id") != snapshot["contest_id"]:
            raise ValueError("Contest mismatch")
        if candidate.get("slate_date") != snapshot["slate_date"]:
            raise ValueError("Slate date mismatch")
        if _parse_time(candidate.get("created_utc")) > _parse_time(snapshot["cutoff_utc"]):
            raise ValueError("Candidate created after cutoff")
        slots = candidate.get("slots")
        if not isinstance(slots, dict) or set(slots) != {"QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DEF"}:
            raise ValueError("Incorrect FanDuel NFL slot pattern")
        ids = list(slots.values())
        if len(set(ids)) != 9 or any(pid not in pool for pid in ids):
            raise ValueError("Duplicate or unknown candidate player")
        salary = 0
        score = 0
        for slot, pid in slots.items():
            p = pool[pid]
            allowed = set(p["positions"])
            needed = "RB" if slot.startswith("RB") else "WR" if slot.startswith("WR") else slot
            if needed == "FLEX":
                if not allowed.intersection({"RB", "WR", "TE"}):
                    raise ValueError("Ineligible FLEX")
            elif needed not in allowed:
                raise ValueError(f"Ineligible player at {slot}")
            salary += p["salary"]
            score += p["projection_fd"]
        if salary > snapshot.get("salary_cap", 60000):
            raise ValueError("Salary cap exceeded")
        results.append({"candidate_id": candidate["candidate_id"], "projected_fd": round(score, 3), "salary": salary})
    return sorted(results, key=lambda x: (-x["projected_fd"], x["candidate_id"]))
