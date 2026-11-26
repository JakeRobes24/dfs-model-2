"""Check original four NFL preliminary candidates without inventing full-pool rankings."""
import json
import unittest
from collections import Counter
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "tests/fixtures/nov22_2026_nfl_four_preliminary_candidates.json").read_text())


class OriginalCandidateTests(unittest.TestCase):
    def test_all_four_candidates_have_nine_unique_players(self):
        self.assertEqual(len(DATA["lineups"]), 4)
        for lineup in DATA["lineups"]:
            with self.subTest(lineup=lineup["label"]):
                self.assertEqual(len(lineup["players"]), 9)
                self.assertEqual(len(set(lineup["players"])), 9)

    def test_salaries_match_original_candidate_totals(self):
        salaries = DATA["all_player_salaries"]
        for lineup in DATA["lineups"]:
            with self.subTest(lineup=lineup["label"]):
                self.assertEqual(sum(salaries[p] for p in lineup["players"]), lineup["salary_total"])
                self.assertLessEqual(lineup["salary_total"], DATA["salary_cap"])
        self.assertEqual([x["salary_total"] for x in DATA["lineups"]], [60000, 60000, 60000, 59800])

    def test_preliminary_scores_and_exposure(self):
        self.assertEqual([x["projected_fd"] for x in DATA["lineups"]], [137.1, 135.9, 135.6, 135.4])
        counts = Counter(p for x in DATA["lineups"] for p in x["players"])
        self.assertEqual(
            {p for p, n in counts.items() if n == 4},
            {"Emmett Johnson", "Parker Washington", "Jalen Coker", "Colston Loveland"},
        )

    def test_original_entered_lineup_matches_primary_fixture(self):
        primary = json.loads((Path(__file__).parent / "tests/fixtures/nov22_2026_nfl_fd_preliminary.json").read_text())
        entered = DATA["lineups"][0]
        self.assertEqual(entered["players"], [r["player"] for r in primary["lineup"]])
        self.assertEqual(entered["salary_total"], sum(r["salary"] for r in primary["lineup"]))
        self.assertEqual(entered["projected_fd"], primary["projected_total_fd"])


if __name__ == "__main__":
    unittest.main()
