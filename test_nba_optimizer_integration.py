"""Deterministic optimizer integration contract with a synthetic eligible pool.

This checks lineup legality, diversity, and objective ordering, not slate accuracy.
"""
import unittest
import pandas as pd
from model import SLOTS, allowed_slots, optimize


def fixture_pool():
    # All nine FanDuel slots are eligible; 36 unique players provide alternatives.
    rows = []
    for i in range(36):
        rows.append({
            "fanduel_id": f"fixture-{i}",
            "fanduel_name": f"Fixture Player {i}",
            "salary": 6000,
            "roster_eligibility": "C/PG/SG/SF/PF/F/G/UTIL",
            "eligible": True,
            "adjusted_fd_points": float(50 - i),
            "adjusted_minutes": 30.0,
            "confidence": "high",
            "minutes_method": "fixture",
            "injury_flag": "",
        })
    return pd.DataFrame(rows)


class OptimizerIntegrationTests(unittest.TestCase):
    def test_four_legal_distinct_lineups(self):
        pool = fixture_pool()
        result = optimize(pool, number=4, max_overlap=7)
        self.assertEqual(len(result), 36, "Expected exactly four complete nine-player lineups")
        self.assertEqual(set(result.lineup), {1, 2, 3, 4})
        rosters = []
        for _, lineup in result.groupby("lineup"):
            self.assertEqual(len(lineup), 9)
            self.assertEqual(lineup.fanduel_id.nunique(), 9)
            self.assertEqual(lineup.slot.tolist().count("UTIL"), 2)
            self.assertEqual(sorted(lineup.slot.tolist()), sorted(SLOTS))
            self.assertLessEqual(int(lineup.salary.sum()), 60000)
            for player in lineup.itertuples():
                eligibility = pool.loc[pool.fanduel_id.eq(player.fanduel_id), "roster_eligibility"].iloc[0]
                self.assertIn(player.slot, allowed_slots(eligibility))
            rosters.append(set(lineup.fanduel_id))
        for i, roster in enumerate(rosters):
            for other in rosters[i+1:]:
                self.assertLessEqual(len(roster & other), 7)

    def test_objective_ranks_first_lineup_at_pool_maximum(self):
        pool = fixture_pool()
        result = optimize(pool, number=1)
        self.assertEqual(len(result), 9)
        self.assertEqual(set(result.fanduel_id), set(pool.nlargest(9, "adjusted_fd_points").fanduel_id))
        self.assertAlmostEqual(float(result.adjusted_fd_points.sum()), sum(range(42, 51)))

    def test_center_slot_survives_pf_slash_c(self):
        self.assertIn("C", allowed_slots("PF/C/UTIL"))
        self.assertIn("PF", allowed_slots("PF/C/UTIL"))

    def test_out_players_never_selected(self):
        pool = fixture_pool()
        pool.loc[0, "eligible"] = False
        pool.loc[0, "injury_flag"] = "O"
        result = optimize(pool, number=1)
        self.assertNotIn("fixture-0", set(result.fanduel_id))


if __name__ == "__main__":
    unittest.main()
