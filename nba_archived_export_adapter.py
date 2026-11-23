"""Adapter for preserved Nov 20-style DFS Model 2.0 CSV archives.

Historical comparisons are retrospective unless independent pre-lock timestamps
and source provenance have been verified. DNPs are excluded from played-player
accuracy, never silently treated as scored zero.
"""
import pandas as pd
from nba_archived_slate_audit import audit_archived_slate


def audit_archived_exports(coverage, projections, actuals, *, projection_points="adjusted_fd_points",
                           projection_minutes="adjusted_minutes", timestamp_verified=False):
    required = {
        "coverage": {"fanduel_id"},
        "projections": {"fanduel_id", projection_points, projection_minutes},
        "actuals": {"fanduel_id", "status", "actual_fd_points", "actual_minutes"},
    }
    frames = {"coverage": coverage, "projections": projections, "actuals": actuals}
    for name, cols in required.items():
        if not cols <= set(frames[name]):
            raise ValueError(f"{name} archive is missing columns: {sorted(cols - set(frames[name]))}")
    ids = coverage.fanduel_id.astype("string")
    if ids.isna().any() or ids.str.strip().eq("").any() or ids.duplicated().any():
        raise ValueError("Contest coverage requires unique nonblank player IDs.")
    actual_status = actuals.status.astype("string").str.lower().str.strip()
    if not actual_status.isin(["played", "dnp", "inactive", "did_not_play"]).all():
        raise ValueError("Unknown actuals status; do not infer played/DNP.")
    played = actuals.loc[actual_status.eq("played")].copy()
    nonplayed = actuals.loc[~actual_status.eq("played")].copy()
    scored = projections[["fanduel_id", projection_points, projection_minutes]].rename(columns={
        projection_points: "projected_fd_points", projection_minutes: "projected_minutes"
    })
    report = audit_archived_slate(scored, played, contest_ids=ids.tolist())
    report.update({
        "played_count": int(len(played)),
        "dnp_inactive_count": int(len(nonplayed)),
        "actuals_missing_contest_ids": int(len(set(ids) - set(actuals.fanduel_id))),
        "retrospective_only": not timestamp_verified,
        "projection_source": projection_points,
        "accuracy_denominator": "played players with paired numeric projection and actual",
    })
    # A separate played-only coverage rate is essential: all-contest coverage
    # penalizes DNPs intentionally excluded from the accuracy calculation.
    report["played_paired_rate"] = (report["fully_comparable_players"] / len(played)
                                    if len(played) else 0.0)
    return report
