import unittest
import pandas as pd
from nba_player_decision_audit import audit_player_decisions, summarize_player_decisions


class PlayerDecisionAuditTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame([
            dict(fanduel_id="1-1", eligible=True, verified_outcome="played", daily_points=20,
                 adjusted_fd_points=28, actual_points=30, daily_minutes=20, adjusted_minutes=27, actual_minutes=28),
            dict(fanduel_id="1-2", eligible=True, verified_outcome="played", daily_points=30,
                 adjusted_fd_points=40, actual_points=20, daily_minutes=30, adjusted_minutes=34, actual_minutes=29),
            dict(fanduel_id="1-3", eligible=True, verified_outcome="did_not_play", daily_points=12,
                 adjusted_fd_points=9, actual_points=None, daily_minutes=16, adjusted_minutes=12, actual_minutes=None),
            dict(fanduel_id="1-4", eligible=True, verified_outcome="needs_review", daily_points=20,
                 adjusted_fd_points=30, actual_points=0, daily_minutes=20, adjusted_minutes=30, actual_minutes=0),
            dict(fanduel_id="1-5", eligible=False, verified_outcome="played", daily_points=10,
                 adjusted_fd_points=12, actual_points=30, daily_minutes=20, adjusted_minutes=22, actual_minutes=24),
        ])

    def test_paired_changes_and_dnp(self):
        result = audit_player_decisions(self.fixture()).set_index("fanduel_id")
        self.assertEqual(len(result), 4)
        self.assertAlmostEqual(result.loc["1-1", "points_error_improvement"], 8)
        self.assertAlmostEqual(result.loc["1-2", "points_error_improvement"], -10)
        self.assertAlmostEqual(result.loc["1-3", "points_error_improvement"], 3)
        self.assertEqual(result.loc["1-3", "audit_state"], "confirmed_dnp")
        self.assertTrue(pd.isna(result.loc["1-3", "minutes_error_improvement"]))
        self.assertTrue(pd.isna(result.loc["1-4", "points_error_improvement"]))
        self.assertEqual(result.loc["1-4", "audit_state"], "unresolved")

    def test_summary_and_no_mutation(self):
        data = self.fixture()
        original = data.copy(deep=True)
        result = audit_player_decisions(data)
        pd.testing.assert_frame_equal(data, original)
        summary = summarize_player_decisions(result).set_index("Sample")
        self.assertEqual(summary.loc["Changed projections", "Paired players"], 3)
        self.assertEqual(summary.loc["Changed projections", "Improved"], 2)
        self.assertEqual(summary.loc["Changed projections", "Worsened"], 1)
        self.assertAlmostEqual(summary.loc["Changed projections", "MAE improvement"], 1/3)

    def test_reject_duplicate_and_missing_columns(self):
        data = self.fixture()
        data.loc[1, "fanduel_id"] = "1-1"
        with self.assertRaises(ValueError):
            audit_player_decisions(data)
        with self.assertRaises(ValueError):
            audit_player_decisions(pd.DataFrame({"fanduel_id": ["1-1"]}))


if __name__ == "__main__":
    unittest.main()
