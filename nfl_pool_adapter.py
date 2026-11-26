"""Adapter from reconciled NFL contest rows into the timestamp-gated challenger.

Separate from NBA slate_import: NBA-specific roster/team validation must not
be reused for NFL. This adapter accepts only explicitly mapped NFL rows.
"""
from datetime import datetime, timezone
import math
from nfl_prelock_challenger import validate_snapshot


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if t.tzinfo is None:
        raise ValueError("Timezone required")
    return t.astimezone(timezone.utc)


def build_nfl_snapshot(rows, *, contest_id, slate_date, source_version, cutoff_utc,
                       salary_cap=60000, expected_player_ids=None):
    """Build a full-pool snapshot from pre-reconciled NFL player records.

    Required keys per row: player_id, salary, positions, projection_fd, asof_utc,
    contest_id, slate_date, team, game, status. No estimates are synthesized.
    expected_player_ids, when provided, prevents silent partial-pool comparison.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError("Nonempty reconciled contest rows required")
    cutoff = _utc(cutoff_utc)
    if type(salary_cap) is not int or salary_cap <= 0:
        raise ValueError("Invalid salary cap")
    if expected_player_ids is None:
        raise ValueError("Exact contest player IDs required to prove full-pool coverage")
    if not isinstance(expected_player_ids, (list, tuple, set)) or not expected_player_ids:
        raise ValueError("Expected IDs must be a nonempty collection")
    if len(expected_player_ids) != len(set(expected_player_ids)):
        raise ValueError("Expected IDs must be unique")
    seen = [r.get("player_id") for r in rows]
    if len(seen) != len(set(seen)) or set(seen) != set(expected_player_ids):
        raise ValueError("Pool is incomplete, duplicated or contains noncontest IDs")
    for row in rows:
        if row.get("contest_id") != contest_id or row.get("slate_date") != slate_date:
            raise ValueError("Mixed contest or slate")
        if not row.get("team") or not row.get("game"):
            raise ValueError("Missing team or game")
        if row.get("status", "").lower() in {"out", "inactive", "suspended"}:
            raise ValueError("Excluded player requires explicit exclusion before optimization")
        if _utc(row.get("asof_utc")) > cutoff:
            raise ValueError("Post-cutoff evidence")
    snapshot = {"contest_id": contest_id, "slate_date": slate_date,
                "source_version": source_version, "cutoff_utc": cutoff_utc,
                "salary_cap": salary_cap,
                "players": [{k: row[k] for k in ("player_id", "salary", "positions", "projection_fd", "asof_utc")}
                            for row in rows]}
    validate_snapshot(snapshot)
    return snapshot
