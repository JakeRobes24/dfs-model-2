import unittest
import pandas as pd
from nba_archived_slate_audit import audit_archived_slate


class ArchivedSlateAuditTests(unittest.TestCase):
    def setUp(self):
        self.pre = pd.DataFrame({
            "fanduel_id": ["contest-1", "contest-2", "contest-3"],
            "projected_fd_points": [30, 20, 10],
            "projected_minutes": [30, 25, 15],
        })
        self.actual = pd.DataFrame({
            "fanduel_id": ["contest-1", "contest-2"],
            "actual_fd_points": [35, 10],
            "actual_minutes": [32, 20],
        })

    def test_missing_actuals_not_hidden_by_inner_join(self):
        result = audit_archived_slate(self.pre, self.actual)
        self.assertEqual(result["contest_players"], 3)
        self.assertEqual(result["fully_comparable_players"], 2)
        self.assertEqual(result["missing_actual_rows"], 1)
        self.assertAlmostEqual(result["coverage_rate"], 2/3)
        self.assertAlmostEqual(result["fd_mae"], 7.5)
        self.assertAlmostEqual(result["fd_bias"], 2.5)
        self.assertAlmostEqual(result["minutes_mae"], 3.5)

    def test_missing_prelock_player_reduces_authoritative_coverage(self):
        result = audit_archived_slate(self.pre.head(2), self.actual,
                                      contest_ids=["contest-1", "contest-2", "contest-3"])
        self.assertEqual(result["contest_players"], 3)
        self.assertEqual(result["missing_prelock_rows"], 1)
        self.assertEqual(result["fully_comparable_players"], 2)
        self.assertAlmostEqual(result["coverage_rate"], 2 / 3)

    def test_missing_projection_is_not_misclassified_as_off_contest_actual(self):
        result = audit_archived_slate(self.pre.head(1), self.actual,
                                      contest_ids=["contest-1", "contest-2", "contest-3"])
        self.assertEqual(result["missing_prelock_rows"], 2)
        self.assertEqual(result["actuals_outside_contest"], 0)
        self.assertEqual(result["missing_actual_rows"], 1)
        self.assertEqual(result["incomplete_comparisons"], 2)

    def test_actuals_outside_authoritative_contest_flagged(self):
        outside = self.actual.copy()
        outside.loc[2] = ["other-4", 22, 19]
        result = audit_archived_slate(self.pre, outside,
                                      contest_ids=["contest-1", "contest-2", "contest-3"])
        self.assertEqual(result["actuals_outside_contest"], 1)

    def test_prelock_outside_contest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the contest"):
            audit_archived_slate(self.pre, self.actual,
                                 contest_ids=["contest-1", "contest-2"])

    def test_extra_actuals_flagged_without_expanding_contest(self):
        self.actual.loc[2] = ["different-contest-4", 100, 40]
        result = audit_archived_slate(self.pre, self.actual)
        self.assertEqual(result["actuals_outside_contest"], 1)
        self.assertEqual(result["contest_players"], 3)

    def test_duplicate_actual_ids_fail_closed(self):
        self.actual.loc[2] = ["contest-1", 40, 35]
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_archived_slate(self.pre, self.actual)

    def test_invalid_actual_minutes_excluded_from_complete_coverage(self):
        self.actual.loc[0, "actual_minutes"] = 55
        result = audit_archived_slate(self.pre, self.actual)
        self.assertEqual(result["fully_comparable_players"], 1)
        self.assertEqual(result["incomplete_comparisons"], 2)

    def test_nonnumeric_prediction_excluded_not_fabricated(self):
        self.pre["projected_fd_points"] = self.pre.projected_fd_points.astype(object)
        self.pre.loc[0, "projected_fd_points"] = "unknown"
        result = audit_archived_slate(self.pre, self.actual)
        self.assertEqual(result["fully_comparable_players"], 1)
        self.assertEqual(result["incomplete_comparisons"], 2)


if __name__ == "__main__":
    unittest.main()
