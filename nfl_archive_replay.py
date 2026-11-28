"""Replay archived NFL workload/range comparisons without extracting private data."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from nfl_snap_workload_review import review_snap_workload, review_range_calibration, yardage_ranges

ARCHIVE_SHA256 = "71a020b29e51fcf53ca7e2db68e4e048981a73409c1d1546a7d6c233c237375f"
WORKLOAD_SHA256 = "255475bfa83fd49b5ee81b286fcdbc9d682590f60cf72d7ce394f946aec55dba"
MEMBER = "nfl-final-matched-week-1-11.csv"


def verified_workload(parts, *, archive_sha256=ARCHIVE_SHA256, workload_sha256=WORKLOAD_SHA256):
    """Join explicitly ordered bytes; verify archive and exact CSV before parsing."""
    archive = b"".join(parts)
    if hashlib.sha256(archive).hexdigest() != archive_sha256:
        raise ValueError("Archive SHA-256 mismatch (check part order and completeness).")
    with ZipFile(io.BytesIO(archive)) as source:
        if source.namelist().count(MEMBER) != 1:
            raise ValueError("Expected exactly one workload CSV member.")
        payload = source.read(MEMBER)
    if hashlib.sha256(payload).hexdigest() != workload_sha256:
        raise ValueError("Workload CSV SHA-256 mismatch.")
    return pd.read_csv(io.BytesIO(payload), dtype={"gsis_id": str, "pfr_id": str})


def replay(parts):
    rows = verified_workload(parts)
    details, _ = review_snap_workload(rows)
    ranges = yardage_ranges(details)
    calibrated = review_range_calibration(ranges, asymmetric_challenge=True)
    matched = calibrated.loc[calibrated.policy.eq("Snap/workload × variable efficiency")]
    metrics = ["coverage", "below_p10", "above_p90", "width", "interval_score"]
    summary = matched.groupby(["yardage", "interval"], as_index=False).agg(
        players=("players", "sum"), weeks=("week", "nunique"),
        **{metric: (metric, "mean") for metric in metrics})
    return {"input_rows": len(rows), "archive_sha256": ARCHIVE_SHA256,
            "workload_sha256": WORKLOAD_SHA256,
            "summary": summary.to_dict("records")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts", nargs="+", type=Path, help="ZIP parts in original order")
    args = parser.parse_args()
    print(json.dumps(replay([path.read_bytes() for path in args.parts]), indent=2))
