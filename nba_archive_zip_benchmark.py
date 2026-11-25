"""Run retrospective NBA archive evaluation from existing local ZIP checkpoints.

Usage:
 python nba_archive_zip_benchmark.py ACTUALS.zip SESSION.zip

No data is downloaded, uploaded, or committed. Timestamp provenance is not
verified by this utility; its output is always retrospective.
"""
import argparse
import io
import json
import zipfile

import pandas as pd

from nba_archived_export_adapter import audit_archived_exports
from nba_archive_provenance import verify_prelock_provenance


def _csv(archive, suffix):
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {suffix} in ZIP, found {len(matches)}.")
    return pd.read_csv(io.BytesIO(archive.read(matches[0])))


def benchmark_nov20(actuals_zip, session_zip, *, snapshot_at=None, lock_at=None,
                    source_groups=None):
    """Evaluate archive, optionally validating supplied chronology.

    Caller-supplied metadata never certifies snapshot authenticity.
    Both timestamps and a source group for each projection are required
    to perform chronology validation.
    """
    with zipfile.ZipFile(actuals_zip) as actuals_archive, zipfile.ZipFile(session_zip) as session:
        actuals = _csv(actuals_archive, "nov20_actuals_audit.csv")
        coverage = _csv(session, "nov20_complete_247_player_coverage.csv")
        projections = _csv(session, "nov20_consensus_audit.csv")
    result = audit_archived_exports(coverage, projections, actuals, timestamp_verified=False)
    if snapshot_at is None and lock_at is None and source_groups is None:
        result["provenance"] = {"chronology_valid": False,
                                "authenticity_verified": False,
                                "reason": "No independently verified pre-lock metadata provided"}
    else:
        if snapshot_at is None or lock_at is None or source_groups is None:
            raise ValueError("Both timestamps and source_groups are required together.")
        if len(source_groups) != len(projections):
            raise ValueError("Source group count must match projection row count.")
        snapshot = projections[["fanduel_id"]].copy()
        snapshot["source_group"] = source_groups
        result["provenance"] = verify_prelock_provenance(
            snapshot, lock_at=lock_at, snapshot_at=snapshot_at)
    # Valid chronology alone never turns a retrospective audit into an
    # authenticated pre-lock backtest.
    result["retrospective_only"] = True
    return {key: value for key, value in result.items() if key != "player_errors"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actuals_zip")
    parser.add_argument("session_zip")
    args = parser.parse_args()
    print(json.dumps(benchmark_nov20(args.actuals_zip, args.session_zip), indent=2))
