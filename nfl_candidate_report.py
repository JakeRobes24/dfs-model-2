"""Reproducible, prelock-only descriptive report for archived NFL candidates.

This reports original preliminary scores, salaries, and exposure. It does NOT
claim an optimized lineup or use postgame actual scores to rank candidates.
"""
import json
from collections import Counter
from pathlib import Path

FIXTURE = Path(__file__).parent / "tests/fixtures/nov22_2026_nfl_four_preliminary_candidates.json"


def summarize(data):
    lineups = data["lineups"]
    counts = Counter(player for lineup in lineups for player in lineup["players"])
    return {
        "slate_date": data["slate_date"],
        "contest_id": data["contest_id"],
        "candidate_count": len(lineups),
        "unique_players": len(counts),
        "shared_all_candidates": sorted(p for p, n in counts.items() if n == len(lineups)),
        "exposure_counts": dict(sorted(counts.items())),
        "candidate_scores": [
            {"label": x["label"], "preliminary_projected_fd": x["projected_fd"],
             "salary_total": x["salary_total"], "unused_salary": data["salary_cap"] - x["salary_total"]}
            for x in lineups
        ],
        "projection_spread": round(max(x["projected_fd"] for x in lineups) - min(x["projected_fd"] for x in lineups), 2),
        "limitations": [
            "Preliminary lineup projections are not final pre-lock forecasts",
            "No ownership, covariance, or slate-wide pool recovered",
            "Exposure counts are descriptive, not evidence of suboptimality",
            "Postgame actual points are intentionally excluded",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(summarize(json.loads(FIXTURE.read_text())), indent=2))
