"""Leakage-resistant historical NBA slate evaluation.

Inputs must be immutable pre-lock predictions and separately collected post-slate
actuals. Never substitute actuals into pre-lock model features.
"""
import numpy as np
import pandas as pd


def audit_archived_slate(prelock, actuals, *, contest_ids=None):
    """Return full-pool coverage and accuracy without silently dropping missing rows.

    prelock: fanduel_id, projected_fd_points, projected_minutes
    actuals: fanduel_id, actual_fd_points, actual_minutes
    """
    expected = {"fanduel_id", "projected_fd_points", "projected_minutes"}
    observed = {"fanduel_id", "actual_fd_points", "actual_minutes"}
    if not expected <= set(prelock) or not observed <= set(actuals):
        raise ValueError("Archived audit requires ID, fantasy points, and minutes for both sources.")
    for frame, label in ((prelock, "prelock"), (actuals, "actuals")):
        ids = frame.fanduel_id.astype("string")
        if ids.isna().any() or ids.str.strip().eq("").any() or ids.duplicated().any():
            raise ValueError(f"{label} must contain unique nonblank contest player IDs.")
    # The contest CSV is the authoritative denominator.
    if contest_ids is None:
        authoritative_ids = set(prelock.fanduel_id)
        missing_prelock = 0
    else:
        ids = pd.Series(list(contest_ids), dtype="string")
        if ids.isna().any() or ids.str.strip().eq("").any() or ids.duplicated().any():
            raise ValueError("Contest IDs must be unique and nonblank.")
        authoritative_ids = set(ids)
        missing_prelock = len(authoritative_ids - set(prelock.fanduel_id))
        if set(prelock.fanduel_id) - authoritative_ids:
            raise ValueError("Pre-lock projections contain players outside the contest.")
    p = prelock[list(expected)].copy()
    a = actuals[list(observed)].copy()
    for frame, cols in ((p, ("projected_fd_points", "projected_minutes")),
                        (a, ("actual_fd_points", "actual_minutes"))):
        for col in cols:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            frame[col] = frame[col].where(frame[col].ge(0))
        frame.loc[frame[cols[1]].gt(48), cols[1]] = np.nan
    joined = p.merge(a, on="fanduel_id", how="left", validate="one_to_one", indicator=True)
    actual_ids = set(a.fanduel_id)
    prediction_ids = set(p.fanduel_id)
    usable = joined[["projected_fd_points", "actual_fd_points",
                     "projected_minutes", "actual_minutes"]].notna().all(axis=1)
    scored = joined.loc[usable].copy()
    fd_error = scored.projected_fd_points - scored.actual_fd_points
    minute_error = scored.projected_minutes - scored.actual_minutes
    return {
        "contest_players": int(len(authoritative_ids)),
        "missing_prelock_rows": int(missing_prelock),
        "actual_players": int(len(a)),
        "missing_actual_rows": int(len(authoritative_ids - actual_ids)),
        "actuals_outside_contest": int(len(actual_ids - authoritative_ids)),
        "incomplete_comparisons": int(len(authoritative_ids) - usable.sum()),
        "fully_comparable_players": int(usable.sum()),
        "coverage_rate": float(usable.sum() / len(authoritative_ids)) if authoritative_ids else 0.0,
        "fd_mae": float(fd_error.abs().mean()) if len(scored) else None,
        "fd_bias": float(fd_error.mean()) if len(scored) else None,
        "minutes_mae": float(minute_error.abs().mean()) if len(scored) else None,
        "player_errors": scored.assign(fd_error=fd_error, minutes_error=minute_error),
    }
