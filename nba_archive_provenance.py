"""Strict provenance checks for historical DFS projection snapshots.

The caller must provide independently recorded UTC timestamps. This validates
chronology, not whether timestamps or source claims are independently authentic.
"""
import pandas as pd


def verify_prelock_provenance(projections, *, lock_at, snapshot_at, source_group_col="source_group"):
    if projections.empty:
        raise ValueError("Cannot certify an empty projection snapshot.")
    if "fanduel_id" not in projections:
        raise ValueError("Projection snapshot requires FanDuel IDs.")
    if source_group_col not in projections:
        raise ValueError("Source independence group is required for provenance.")
    ids = projections.fanduel_id.astype("string")
    if ids.isna().any() or ids.str.strip().eq("").any() or ids.duplicated().any():
        raise ValueError("Projection snapshot IDs must be unique and nonblank.")
    groups = projections[source_group_col].astype("string")
    if groups.isna().any() or groups.str.strip().eq("").any():
        raise ValueError("Every projection requires a source independence group.")
    lock = pd.Timestamp(lock_at)
    snapshot = pd.Timestamp(snapshot_at)
    if lock.tzinfo is None or snapshot.tzinfo is None:
        raise ValueError("Lock and snapshot timestamps must be timezone-aware.")
    if snapshot >= lock:
        raise ValueError("Snapshot must be captured strictly before contest lock.")
    return {
        "chronology_valid": True,
        "snapshot_at_utc": snapshot.tz_convert("UTC").isoformat(),
        "lock_at_utc": lock.tz_convert("UTC").isoformat(),
        "source_independence_groups": int(groups.nunique()),
        "projection_rows": int(len(projections)),
        "authenticity_verified": False,
    }
