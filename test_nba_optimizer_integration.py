"""Deterministic optimizer integration contract with a synthetic eligible pool.

This checks lineup legality, diversity, and objective ordering, not slate accuracy.
"""
import unittest
import pandas as pd
from model import SLOTS, allowed_slots, optimize, optimize_late_swap


def fixture_pool():
    # All nine FanDuel slots are eligible; 36 unique players provide alternatives.
    rows = []
    for i in range(36):
        rows.append({
            "fanduel_id": f"fixture-{i}",
            "fanduel_name": f"Fixture Player {i}",
            "salary": 6000,
            "team": ["CHA","BOS","NYK","TOR"][i%4],
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

    def test_salary_cap_changes_optimum(self):
        pool = fixture_pool()
        pool.loc[0, "salary"] = 15000
        result = optimize(pool, number=1)
        self.assertEqual(len(result), 9)
        self.assertLessEqual(int(result.salary.sum()), 60000)
        # Selecting the expensive top scorer alongside eight $6k players
        # would cost $63k; the solver must reject that tempting combination.
        self.assertNotIn("fixture-0", set(result.fanduel_id))

    def test_position_restrictions_are_enforced(self):
        pool = fixture_pool()
        pool["roster_eligibility"] = "UTIL"
        pool.loc[0:6, "roster_eligibility"] = "PG/G/UTIL"
        pool.loc[7:13, "roster_eligibility"] = "SG/G/UTIL"
        pool.loc[14:20, "roster_eligibility"] = "SF/F/UTIL"
        pool.loc[21:27, "roster_eligibility"] = "PF/F/UTIL"
        pool.loc[28:35, "roster_eligibility"] = "C/F/UTIL"
        result = optimize(pool, number=1)
        self.assertEqual(len(result), 9)
        self.assertEqual(sorted(result.slot), sorted(SLOTS))
        for player in result.itertuples():
            eligibility = pool.loc[pool.fanduel_id.eq(player.fanduel_id), "roster_eligibility"].iloc[0]
            self.assertIn(player.slot, allowed_slots(eligibility))

    def test_invalid_locked_slot_is_rejected(self):
        pool = fixture_pool()
        with self.assertRaisesRegex(ValueError, "Locked slots"):
            optimize(pool, number=1, fixed_slots={9: "fixture-0"})

    def test_ineligible_locked_position_is_rejected(self):
        pool = fixture_pool()
        pool.loc[0, "roster_eligibility"] = "C/UTIL"
        with self.assertRaisesRegex(ValueError, "not eligible"):
            optimize(pool, number=1, fixed_slots={0: "fixture-0"})

    def test_out_locked_player_is_rejected(self):
        pool = fixture_pool()
        pool.loc[0, "eligible"] = False
        pool.loc[0, "injury_flag"] = "O"
        with self.assertRaisesRegex(ValueError, "Open-game pinned players require"):
            optimize(pool, number=1, fixed_slots={0: "fixture-0"})

    def test_late_swap_preserves_started_slots_and_replaces_open_player(self):
        pool = fixture_pool()
        entered = optimize(pool, number=1)
        self.assertEqual(len(entered), 9)
        closed_ids = set(entered.head(2).fanduel_id)
        open_id = entered.iloc[2].fanduel_id
        pool.loc[pool.fanduel_id.eq(open_id), "eligible"] = False
        pool.loc[pool.fanduel_id.eq(open_id), "injury_flag"] = "O"
        swapped = optimize_late_swap(pool, entered, closed_ids)
        self.assertEqual(len(swapped), 9)
        self.assertEqual(swapped.fanduel_id.nunique(), 9)
        self.assertEqual(sorted(swapped.slot), sorted(SLOTS))
        self.assertLessEqual(int(swapped.salary.sum()), 60000)
        self.assertNotIn(open_id, set(swapped.fanduel_id))
        self.assertEqual(set(swapped.loc[swapped.locked, "fanduel_id"]), closed_ids)
        for pid in closed_ids:
            original_slot = entered.loc[entered.fanduel_id.eq(pid), "slot"].iloc[0]
            replacement_slot = swapped.loc[swapped.fanduel_id.eq(pid), "slot"].iloc[0]
            self.assertEqual(replacement_slot, original_slot)

    def test_late_swap_rejects_incomplete_entered_lineup(self):
        pool = fixture_pool()
        entered = optimize(pool, number=1).head(8)
        with self.assertRaisesRegex(ValueError, "nine FanDuel slots"):
            optimize_late_swap(pool, entered, {entered.iloc[0].fanduel_id})

    def test_started_out_player_remains_locked(self):
        pool = fixture_pool()
        pool.loc[0, "eligible"] = False
        pool.loc[0, "injury_flag"] = "O"
        pool.loc[0, "adjusted_fd_points"] = 0.0
        result = optimize(pool, number=1, fixed_slots={0: "fixture-0"},
                          closed_players={"fixture-0"})
        locked = result.loc[result.fanduel_id.eq("fixture-0")]
        self.assertEqual(len(result), 9)
        self.assertEqual(len(locked), 1)
        self.assertEqual(locked.iloc[0].slot, "PG")

    def test_insufficient_players_does_not_return_invalid_roster(self):
        pool = fixture_pool().head(8)
        result = optimize(pool, number=1)
        self.assertTrue(result.empty)

    def test_blocked_pair_is_not_selected_together(self):
        pool = fixture_pool()
        result = optimize(pool, number=1, blocked_pairs=[("Fixture Player 0", "Fixture Player 1")])
        selected = set(result.player)
        self.assertFalse({"Fixture Player 0", "Fixture Player 1"} <= selected)

    def test_alternative_objective_is_respected(self):
        pool = fixture_pool()
        pool["ceiling_fd_points"] = pool.adjusted_fd_points
        pool.loc[35, "ceiling_fd_points"] = 200.0
        result = optimize(pool, number=1, objective_column="ceiling_fd_points")
        self.assertIn("fixture-35", set(result.fanduel_id))

    def test_out_players_never_selected(self):
        pool = fixture_pool()
        pool.loc[0, "eligible"] = False
        pool.loc[0, "injury_flag"] = "O"
        result = optimize(pool, number=1)
        self.assertNotIn("fixture-0", set(result.fanduel_id))


if __name__ == "__main__":
    unittest.main()
