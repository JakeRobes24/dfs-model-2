"""Player-level paired audit of frozen NBA projections and actual results.

This module never modifies the frozen input or learns new projection weights.
Unresolved outcomes remain missing, and confirmed DNPs contribute zero points.
"""
import numpy as np
import pandas as pd

REQUIRED = {"fanduel_id", "eligible", "verified_outcome", "daily_points",
            "adjusted_fd_points", "actual_points", "daily_minutes",
            "adjusted_minutes", "actual_minutes"}


def audit_player_decisions(replay):
    if not REQUIRED <= set(replay):
        raise ValueError("Frozen replay is missing required player audit columns.")
    if replay.fanduel_id.isna().any() or not replay.fanduel_id.is_unique:
        raise ValueError("Player audit requires unique nonmissing FanDuel IDs.")
    rows = replay.loc[replay.eligible.eq(True)].copy()
    played = rows.verified_outcome.eq("played")
    dnp = rows.verified_outcome.eq("did_not_play")
    rows["actual_points_audit"] = pd.to_numeric(rows.actual_points, errors="coerce")
    rows.loc[dnp, "actual_points_audit"] = 0.0
    rows.loc[~(played | dnp), "actual_points_audit"] = np.nan
    for col in ("daily_points", "adjusted_fd_points", "daily_minutes", "adjusted_minutes", "actual_minutes"):
        rows[col] = pd.to_numeric(rows[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    paired = (rows[["daily_points", "adjusted_fd_points", "actual_points_audit"]].notna().all(axis=1)
              & np.isfinite(rows["actual_points_audit"]))
    rows["daily_absolute_error"] = (rows.daily_points - rows.actual_points_audit).abs().where(paired)
    rows["adjusted_absolute_error"] = (rows.adjusted_fd_points - rows.actual_points_audit).abs().where(paired)
    rows["points_error_improvement"] = (rows.daily_absolute_error - rows.adjusted_absolute_error)
    rows["projection_change"] = rows.adjusted_fd_points - rows.daily_points
    rows["changed_projection"] = rows.projection_change.abs().gt(.01)
    minutes_paired = played & rows[["daily_minutes", "adjusted_minutes", "actual_minutes"]].notna().all(axis=1)
    rows["daily_minutes_error"] = (rows.daily_minutes - rows.actual_minutes).where(minutes_paired)
    rows["adjusted_minutes_error"] = (rows.adjusted_minutes - rows.actual_minutes).where(minutes_paired)
    rows["minutes_error_improvement"] = (rows.daily_minutes_error.abs() - rows.adjusted_minutes_error.abs())
    rows["audit_state"] = np.select(
        [~(played | dnp), ~paired, dnp, played],
        ["unresolved", "missing_points_pair", "confirmed_dnp", "played"],
        default="unresolved")
    columns = ["fanduel_id"]
    columns += [col for col in ("fanduel_name", "team", "game", "minutes_method", "projection_method") if col in rows]
    columns += ["audit_state", "daily_points", "adjusted_fd_points", "actual_points_audit",
                "projection_change", "changed_projection", "daily_absolute_error",
                "adjusted_absolute_error", "points_error_improvement", "daily_minutes",
                "adjusted_minutes", "actual_minutes", "daily_minutes_error",
                "adjusted_minutes_error", "minutes_error_improvement"]
    return rows[columns].sort_values(["changed_projection", "fanduel_id"], ascending=[False, True]).reset_index(drop=True)


def summarize_player_decisions(audit):
    paired = audit.loc[audit.points_error_improvement.notna()]
    changed = paired.loc[paired.changed_projection]
    def describe(rows, label):
        diffs = rows.points_error_improvement
        return {"Sample": label, "Paired players": len(rows),
                "Improved": int((diffs > .01).sum()), "Worsened": int((diffs < -.01).sum()),
                "Tied": int(diffs.abs().le(.01).sum()),
                "DAILY MAE": rows.daily_absolute_error.mean(),
                "Adjusted MAE": rows.adjusted_absolute_error.mean(),
                "MAE improvement": diffs.mean()}
    return pd.DataFrame([describe(paired, "All paired players"), describe(changed, "Changed projections")])
