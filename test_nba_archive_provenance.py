import unittest
import pandas as pd
from nba_archive_provenance import verify_prelock_provenance


class ArchiveProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.projections = pd.DataFrame({
            "fanduel_id": ["a", "b"],
            "source_group": ["daily", "independent-research"],
        })
        self.kwargs = {
            "snapshot_at": "2026-11-20T18:00:00-05:00",
            "lock_at": "2026-11-20T19:00:00-05:00",
        }

    def test_valid_chronology_reports_no_authenticity_certification(self):
        result = verify_prelock_provenance(self.projections, **self.kwargs)
        self.assertTrue(result["chronology_valid"])
        self.assertFalse(result["authenticity_verified"])
        self.assertEqual(result["source_independence_groups"], 2)

    def test_after_lock_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly before"):
            verify_prelock_provenance(self.projections,
                                      snapshot_at="2026-11-20T20:00:00-05:00",
                                      lock_at=self.kwargs["lock_at"])

    def test_equal_to_lock_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly before"):
            verify_prelock_provenance(self.projections,
                                      snapshot_at=self.kwargs["lock_at"],
                                      lock_at=self.kwargs["lock_at"])

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            verify_prelock_provenance(self.projections,
                                      snapshot_at="2026-11-20 18:00",
                                      lock_at=self.kwargs["lock_at"])

    def test_missing_source_group_rejected(self):
        with self.assertRaisesRegex(ValueError, "independence group"):
            verify_prelock_provenance(self.projections.drop(columns=["source_group"]),
                                      **self.kwargs)

    def test_blank_source_group_rejected(self):
        self.projections.loc[0, "source_group"] = " "
        with self.assertRaisesRegex(ValueError, "independence group"):
            verify_prelock_provenance(self.projections, **self.kwargs)

    def test_duplicate_ids_rejected(self):
        self.projections.loc[1, "fanduel_id"] = "a"
        with self.assertRaisesRegex(ValueError, "unique"):
            verify_prelock_provenance(self.projections, **self.kwargs)


if __name__ == "__main__":
    unittest.main()
