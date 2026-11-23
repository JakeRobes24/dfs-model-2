"""Fail-closed NFL contest -> projections -> prelock challenger pipeline.

Retain full imported pool for coverage; exclude official OUT players from the
candidate pool only after documenting their exclusion. Never backfill missing
individual projections from aggregate lineup totals.
"""
from nfl_contest_import import import_nfl_contest, attach_nfl_projections
from nfl_pool_adapter import build_nfl_snapshot
from nfl_prelock_challenger import compare_prelock_candidates


def run_nfl_prelock_pipeline(contest_csv, projections, candidates, *,
                             contest_id, slate_date, source_version, cutoff_utc):
    contest = import_nfl_contest(contest_csv, expected_contest_id=contest_id)
    reconciled = attach_nfl_projections(contest, projections, slate_date=slate_date,
                                        source_version=source_version)
    excluded = [p["player_id"] for p in reconciled if p["status"] == "out"]
    active = [p for p in reconciled if p["status"] != "out"]
    missing = [p["player_id"] for p in active if p["projection_fd"] is None or not p["asof_utc"]]
    report = {"contest_id": str(contest_id), "slate_date": slate_date,
              "contest_players": len(contest), "excluded_out_ids": excluded,
              "eligible_players": len(active), "missing_projection_ids": missing,
              "ready": False, "rankings": []}
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
    return report
