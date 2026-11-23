import unittest
import pandas as pd
from nba_archived_export_adapter import audit_archived_exports


class ArchivedExportAdapterTests(unittest.TestCase):
    def setUp(self):
        self.coverage = pd.DataFrame({"fanduel_id": ["c-1", "c-2", "c-3"]})
        self.projections = pd.DataFrame({
            "fanduel_id": ["c-1", "c-2"],
            "adjusted_fd_points": [20, 15],
            "adjusted_minutes": [25, 20],
        })
        self.actuals = pd.DataFrame({
            "fanduel_id": ["c-1", "c-2", "c-3"],
            "status": ["played", "did_not_play", "played"],
            "actual_fd_points": [25, None, 10],
            "actual_minutes": [28, None, 12],
        })

    def test_dnp_separate_and_missing_projection_visible(self):
        result = audit_archived_exports(self.coverage, self.projections, self.actuals)
        self.assertEqual(result["contest_players"], 3)
        self.assertEqual(result["played_count"], 2)
        self.assertEqual(result["dnp_inactive_count"], 1)
        self.assertEqual(result["missing_prelock_rows"], 1)
        self.assertEqual(result["fully_comparable_players"], 1)
        self.assertAlmostEqual(result["played_paired_rate"], .5)
        self.assertTrue(result["retrospective_only"])

    def test_explicit_provenance_override(self):
        result = audit_archived_exports(self.coverage, self.projections, self.actuals,
                                        timestamp_verified=True)
        self.assertFalse(result["retrospective_only"])

    def test_unknown_status_fails_closed(self):
        self.actuals.loc[0, "status"] = "maybe"
        with self.assertRaisesRegex(ValueError, "Unknown actuals status"):
            audit_archived_exports(self.coverage, self.projections, self.actuals)


if __name__ == "__main__":
    unittest.main()
