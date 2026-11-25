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
    # Symmetric attribution: actual minus forecast, split into minutes and rate.
    # Compare DAILY and reviewed on the identical verified played-player sample.
    # Negative actual fantasy points are valid; zero minutes never defines a rate.
    source = rows.get("nba_source", pd.Series("", index=rows.index))
    valid = (played & source.fillna("").astype(str).str.strip().ne("")
             & rows[["daily_points", "adjusted_fd_points", "actual_points_audit"]]
                   .apply(lambda col: np.isfinite(col)).all(axis=1)
             & rows[["daily_minutes", "adjusted_minutes", "actual_minutes"]]
                   .apply(lambda col: col.gt(0) & col.le(60)).all(axis=1))
    actual_minutes = rows.actual_minutes.where(valid)
    actual_rate = rows.actual_points_audit.where(valid) / actual_minutes
    rows["actual_fppm"] = actual_rate
    for prefix, point_col, minute_col in [
        ("daily", "daily_points", "daily_minutes"),
        ("adjusted", "adjusted_fd_points", "adjusted_minutes"),
    ]:
        minutes = rows[minute_col].where(valid)
        rate = rows[point_col].where(valid) / minutes
        time_effect = (actual_minutes - minutes) * (actual_rate + rate) / 2
        rate_effect = (actual_rate - rate) * (actual_minutes + minutes) / 2
        rows[f"{prefix}_fppm"] = rate
        rows[f"{prefix}_minutes_effect"] = time_effect
        rows[f"{prefix}_rate_effect"] = rate_effect
        small = time_effect.abs().lt(.01) & rate_effect.abs().lt(.01)
        rows[f"{prefix}_error_driver"] = np.select(
            [~valid, small, time_effect.abs().ge(2 * rate_effect.abs()),
             rate_effect.abs().ge(2 * time_effect.abs())],
            ["unsupported", "negligible", "minutes", "rate"],
            default="mixed")
    columns = ["fanduel_id"]
    columns += [col for col in ("fanduel_name", "team", "game", "minutes_method", "projection_method") if col in rows]
    columns += ["audit_state", "daily_points", "adjusted_fd_points", "actual_points_audit",
                "projection_change", "changed_projection", "daily_absolute_error",
                "adjusted_absolute_error", "points_error_improvement", "daily_minutes",
                "adjusted_minutes", "actual_minutes", "daily_minutes_error",
                "adjusted_minutes_error", "minutes_error_improvement",
                "actual_fppm", "daily_fppm", "adjusted_fppm",
                "daily_minutes_effect", "daily_rate_effect", "daily_error_driver",
                "adjusted_minutes_effect", "adjusted_rate_effect", "adjusted_error_driver"]
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


def summarize_error_attribution(audit):
    """Describe error components on identical supported rows, never learn weights."""
    rows = []
    for prefix, label in (("daily", "DAILY"), ("adjusted", "Reviewed")):
        paired = audit.loc[audit[f"{prefix}_minutes_effect"].notna()
                           & audit[f"{prefix}_rate_effect"].notna()]
        time, rate = paired[f"{prefix}_minutes_effect"], paired[f"{prefix}_rate_effect"]
        driver = paired[f"{prefix}_error_driver"]
        rows.append({"Forecast": label, "Paired players": len(paired),
                     "Mean absolute minutes effect": time.abs().mean(),
                     "Mean absolute rate effect": rate.abs().mean(),
                     "Mean signed minutes effect": time.mean(),
                     "Mean signed rate effect": rate.mean(),
                     "Minutes-led": int(driver.eq("minutes").sum()),
                     "Rate-led": int(driver.eq("rate").sum()),
                     "Mixed": int(driver.eq("mixed").sum()),
                     "Negligible": int(driver.eq("negligible").sum())})
    return pd.DataFrame(rows)
