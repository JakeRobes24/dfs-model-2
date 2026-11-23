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


def _csv(archive, suffix):
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {suffix} in ZIP, found {len(matches)}.")
    return pd.read_csv(io.BytesIO(archive.read(matches[0])))


def benchmark_nov20(actuals_zip, session_zip):
    with zipfile.ZipFile(actuals_zip) as actuals_archive, zipfile.ZipFile(session_zip) as session:
        actuals = _csv(actuals_archive, "nov20_actuals_audit.csv")
        coverage = _csv(session, "nov20_complete_247_player_coverage.csv")
        projections = _csv(session, "nov20_consensus_audit.csv")
    result = audit_archived_exports(coverage, projections, actuals, timestamp_verified=False)
    return {key: value for key, value in result.items() if key != "player_errors"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actuals_zip")
    parser.add_argument("session_zip")
    args = parser.parse_args()
    print(json.dumps(benchmark_nov20(args.actuals_zip, args.session_zip), indent=2))
