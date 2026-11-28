import json
import unittest
from pathlib import Path
from nfl_candidate_report import summarize


class CandidateReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((Path(__file__).parent / "tests/fixtures/nov22_2026_nfl_four_preliminary_candidates.json").read_text())

    def test_report_exposure_and_projection_spread(self):
        result = summarize(self.fixture)
        self.assertEqual(result["candidate_count"], 4)
        self.assertEqual(result["projection_spread"], 1.7)
        self.assertEqual(result["shared_all_candidates"], ["Colston Loveland", "Emmett Johnson", "Jalen Coker", "Parker Washington"])
        self.assertEqual([x["unused_salary"] for x in result["candidate_scores"]], [0, 0, 0, 200])

    def test_report_does_not_consume_actual_results(self):
        before = summarize(self.fixture)
        self.fixture["actual_total_fd"] = 9999
        self.fixture["lineups"][0]["actual_fd"] = 9999
        self.assertEqual(before, summarize(self.fixture))


if __name__ == "__main__":
    unittest.main()
