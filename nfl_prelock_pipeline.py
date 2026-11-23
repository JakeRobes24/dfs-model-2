"""Fail-closed NFL contest -> projections -> prelock challenger pipeline.

Retain full imported pool for coverage; exclude official OUT players from the
candidate pool only after documenting their exclusion. Never backfill missing
individual projections from aggregate lineup totals.
"""
from datetime import datetime, timezone
from nfl_contest_import import import_nfl_contest, attach_nfl_projections
from nfl_pool_adapter import build_nfl_snapshot
from nfl_prelock_challenger import compare_prelock_candidates


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo is not None else None


def run_nfl_prelock_pipeline(contest_csv, projections, candidates, *,
                             contest_id, slate_date, source_version, cutoff_utc, official_status_evidence=None):
    contest = import_nfl_contest(contest_csv, expected_contest_id=contest_id)
    reconciled = attach_nfl_projections(contest, projections, slate_date=slate_date,
                                        source_version=source_version)
    excluded = [p["player_id"] for p in reconciled if p["status"] == "out"]
    active = [p for p in reconciled if p["status"] != "out"]
    missing = [p["player_id"] for p in active if p["projection_fd"] is None or not p["asof_utc"]]
    # A named projection version alone is not evidence of an independently
    # traceable source. Keep legacy readiness separate from certification.
    projection_by_id = {p["player_id"]: p for p in projections}
    cutoff = _timestamp(cutoff_utc)
    if cutoff is None:
        raise ValueError("Timezone-aware cutoff required")
    unverified = [
        p["player_id"] for p in active
        if not projection_by_id.get(p["player_id"], {}).get("source")
        or not projection_by_id.get(p["player_id"], {}).get("source_version")
        or not projection_by_id.get(p["player_id"], {}).get("source_record_id")
        or _timestamp(projection_by_id.get(p["player_id"], {}).get("asof_utc")) is None
    ]
    # Contest injury flags cannot independently certify official availability.
    evidence = official_status_evidence if official_status_evidence is not None else []
    if not isinstance(evidence, list):
        raise ValueError("Official status evidence must be a list")
    official_by_id = {}
    contest_ids = {p["player_id"] for p in contest}
    for entry in evidence:
        pid = entry.get("player_id")
        if not pid or pid in official_by_id or pid not in contest_ids:
            raise ValueError("Official status evidence IDs must be unique and on-contest")
        official_by_id[pid] = entry
    # An official OUT report overrides a stale/blank contest injury flag.
    # Never rank a lineup while its eligible pool contains a known inactive.
    conflicting_out = []
    for p in active:
        entry = official_by_id.get(p["player_id"], {})
        stamp = _timestamp(entry.get("observed_at"))
        if (entry.get("official") is True and entry.get("source")
                and entry.get("source_record_id") and stamp is not None
                and stamp <= cutoff
                and str(entry.get("status", "")).lower() in
                {"out", "inactive", "ir", "suspended"}):
            conflicting_out.append(p["player_id"])
    uncertain_status = []
    for p in active:
        entry = official_by_id.get(p["player_id"], {})
        stamp = _timestamp(entry.get("observed_at"))
        if (entry.get("status", "").lower() not in {"active", "available"}
                or entry.get("official") is not True
                or not entry.get("source")
                or not entry.get("source_record_id")
                or stamp is None or stamp > cutoff):
            uncertain_status.append(p["player_id"])
    report = {"contest_id": str(contest_id), "slate_date": slate_date,
              "contest_players": len(contest), "excluded_out_ids": excluded,
              "eligible_players": len(active), "missing_projection_ids": missing,
              "ready": False, "certified": False, "rankings": [],
              "unverified_projection_ids": unverified,
              "uncertain_status_ids": uncertain_status,
              "officially_out_conflict_ids": conflicting_out}
    if conflicting_out:
        report["block_reason"] = "Official inactive evidence conflicts with contest eligibility"
        return report
    if missing:
        report["block_reason"] = "Missing individually timestamped projections"
        return report
    if not active:
        report["block_reason"] = "No eligible contest players"
        return report
    snapshot = build_nfl_snapshot(
        active, contest_id=str(contest_id), slate_date=slate_date,
        source_version=source_version, cutoff_utc=cutoff_utc,
        expected_player_ids=[p["player_id"] for p in active])
    report["rankings"] = compare_prelock_candidates(snapshot, candidates)
    report["ready"] = True
    report["certified"] = not unverified and not uncertain_status
    if not report["certified"]:
        report["certification_warning"] = (
            "Preliminary comparison only: projection provenance or player status "
            "is not independently verified"
        )
    return report
