import unittest
from nfl_replay_coverage import audit_nfl_replay_coverage
from test_nfl_prelock_pipeline import inputs


class NFLReplayCoverageTests(unittest.TestCase):
    def test_full_pool_without_actuals(self):
        csv, projections, candidates, kw = inputs()
        report = audit_nfl_replay_coverage(
            csv, projections, candidates, contest_id=kw["contest_id"])
        self.assertEqual(report["eligible_players"], 9)
        self.assertEqual(report["projection_covered"], 9)
        self.assertEqual(report["actuals_covered"], 0)
        self.assertTrue(report["full_prelock_replay_ready"])
        self.assertFalse(report["full_postslate_audit_ready"])

    def test_missing_projection_blocks_full_replay(self):
        csv, projections, candidates, kw = inputs()
        report = audit_nfl_replay_coverage(
            csv, projections[:-1], candidates, contest_id=kw["contest_id"])
        self.assertFalse(report["full_prelock_replay_ready"])
        self.assertEqual(report["missing_candidate_projection_ids"], ["136799-9"])

    def test_full_actuals_ready(self):
        csv, projections, candidates, kw = inputs()
        actuals = [{"player_id": p["player_id"], "actual_fd": 0}
                   for p in projections]
        report = audit_nfl_replay_coverage(
            csv, projections, candidates, contest_id=kw["contest_id"], actuals=actuals)
        self.assertTrue(report["full_postslate_audit_ready"])
        self.assertEqual(report["actuals_covered"], 9)

    def test_duplicate_actual_rejected(self):
        csv, projections, candidates, kw = inputs()
        with self.assertRaises(ValueError):
            audit_nfl_replay_coverage(
                csv, projections, candidates, contest_id=kw["contest_id"],
                actuals=[{"player_id": "136799-1", "actual_fd": 2}] * 2)

    def test_out_of_contest_candidate_rejected(self):
        csv, projections, candidates, kw = inputs()
        candidates[0]["slots"]["QB"] = "999999-1"
        with self.assertRaises(ValueError):
            audit_nfl_replay_coverage(
                csv, projections, candidates, contest_id=kw["contest_id"])


if __name__ == "__main__":
    unittest.main()
