import io
import tempfile
import unittest
import zipfile

import pandas as pd

from nba_archive_zip_benchmark import benchmark_nov20


class ArchiveZipBenchmarkTests(unittest.TestCase):
    def test_zip_round_trip(self):
        coverage = pd.DataFrame({"fanduel_id": ["c-1", "c-2"]})
        projection = pd.DataFrame({"fanduel_id": ["c-1"],
                                   "adjusted_fd_points": [20],
                                   "adjusted_minutes": [25]})
        actual = pd.DataFrame({"fanduel_id": ["c-1", "c-2"],
                               "status": ["played", "did_not_play"],
                               "actual_fd_points": [24, None],
                               "actual_minutes": [26, None]})
        with tempfile.TemporaryDirectory() as directory:
            actual_path, session_path = directory + "/actual.zip", directory + "/session.zip"
            with zipfile.ZipFile(actual_path, "w") as z:
                z.writestr("nov20_actuals_audit.csv", actual.to_csv(index=False))
            with zipfile.ZipFile(session_path, "w") as z:
                z.writestr("backup/nov20_complete_247_player_coverage.csv", coverage.to_csv(index=False))
                z.writestr("backup/nov20_consensus_audit.csv", projection.to_csv(index=False))
            result = benchmark_nov20(actual_path, session_path)
        self.assertEqual(result["contest_players"], 2)
        self.assertEqual(result["played_count"], 1)
        self.assertEqual(result["dnp_inactive_count"], 1)
        self.assertEqual(result["fully_comparable_players"], 1)
        self.assertEqual(result["fd_mae"], 4)
        self.assertTrue(result["retrospective_only"])
        self.assertNotIn("player_errors", result)


if __name__ == "__main__":
    unittest.main()
