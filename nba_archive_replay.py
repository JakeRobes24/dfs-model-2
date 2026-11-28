"""Reproduce NBA history-window challengers from a pinned official archive."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from nba_history_windows import compare_history_windows
from nba_rate_distribution import compare_rate_distributions, calibrate_rate_ranges
from nba_group_dependence import compare_groups
from nba_history_ranges import historical_forecasts

ARCHIVE_SHA256 = "2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9"
MEMBER = "official_played_observations.json"


def verified_observations(payload, *, archive_sha256=ARCHIVE_SHA256):
    if hashlib.sha256(payload).hexdigest() != archive_sha256:
        raise ValueError("NBA archive SHA-256 mismatch.")
    with ZipFile(io.BytesIO(payload)) as source:
        if source.namelist().count(MEMBER) != 1:
            raise ValueError("Expected exactly one official observations member.")
        records = json.loads(source.read(MEMBER))
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise ValueError("Expected player-game observation records.")
    return records


def replay(payload, *, cutoff_day="2026-11-26"):
    records = verified_observations(payload)
    result = compare_history_windows(records, cutoff_day=cutoff_day,
                                     short_long_challenge=True, rate_challenge=True,
                                     component_challenge=True)
    distribution = compare_rate_distributions(records, cutoff_day=cutoff_day)
    return {"archive_sha256": ARCHIVE_SHA256, "input_rows": len(records),
            "group_dependence": compare_groups(historical_forecasts(records, cutoff_day=cutoff_day))["summary"],
            "rate_distribution": distribution["summary"],
            "rate_calibration": calibrate_rate_ranges(distribution["rows"]),
            "cutoff_day": cutoff_day, "summary": result["summary"],
            "rejected": result["rejected"], "certified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--cutoff-day", default="2026-11-26")
    args = parser.parse_args()
    print(json.dumps(replay(args.archive.read_bytes(), cutoff_day=args.cutoff_day), indent=2))
