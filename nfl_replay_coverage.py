"""Auditable NFL historical replay coverage without invented missing values."""
from nfl_contest_import import import_nfl_contest


def audit_nfl_replay_coverage(contest_csv, projections, candidates, *,
                              contest_id, actuals=None):
    pool = import_nfl_contest(contest_csv, expected_contest_id=contest_id)
    ids = {p["player_id"] for p in pool}
    if not isinstance(projections, list) or not isinstance(candidates, list):
        raise ValueError("Projections and candidates must be lists")
    if actuals is not None and not isinstance(actuals, list):
        raise ValueError("Actuals must be a list when provided")
    def index(items, label):
        result = {}
        for item in items:
            pid = item.get("player_id")
            if not pid or pid in result or pid not in ids:
                raise ValueError(f"{label} contains duplicate, unknown, or missing player ID")
            result[pid] = item
        return result
    projected = index(projections, "Projections")
    observed = index(actuals or [], "Actuals")
    available = [p for p in pool if p["status"] != "out"]
    missing_projections = sorted(
        p["player_id"] for p in available
        if projected.get(p["player_id"], {}).get("projection_fd") is None
        or not projected.get(p["player_id"], {}).get("asof_utc"))
    missing_actuals = sorted(
        p["player_id"] for p in available
        if observed.get(p["player_id"], {}).get("actual_fd") is None)
    candidate_ids = set()
    for candidate in candidates:
        slots = candidate.get("slots")
        if not isinstance(slots, dict):
            raise ValueError("Candidate slots must be a dictionary")
        for pid in slots.values():
            if pid not in ids:
                raise ValueError("Candidate references player outside contest")
            candidate_ids.add(pid)
    missing_candidate_projections = sorted(candidate_ids.intersection(missing_projections))
    missing_candidate_actuals = sorted(candidate_ids.intersection(missing_actuals))
    return {
        "contest_id": str(contest_id),
        "contest_players": len(pool),
        "eligible_players": len(available),
        "excluded_out_players": len(pool) - len(available),
        "projection_covered": len(available) - len(missing_projections),
        "actuals_covered": len(available) - len(missing_actuals),
        "missing_projection_ids": missing_projections,
        "missing_actual_ids": missing_actuals,
        "candidate_player_count": len(candidate_ids),
        "missing_candidate_projection_ids": missing_candidate_projections,
        "missing_candidate_actual_ids": missing_candidate_actuals,
        "full_prelock_replay_ready": not missing_projections and bool(available),
        "full_postslate_audit_ready": not missing_projections and not missing_actuals and bool(available),
    }
