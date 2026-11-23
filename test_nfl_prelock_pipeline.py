import unittest
from nfl_prelock_pipeline import run_nfl_prelock_pipeline

HEAD="Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator"
POS=["QB","RB","RB","WR","WR","WR","TE","RB","D","WR"]
ROSTER=["QB","RB/FLEX","RB/FLEX","WR/FLEX","WR/FLEX","WR/FLEX","TE/FLEX","RB/FLEX","DEF","WR/FLEX"]
SLOTS=["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DEF"]
TIME="2026-11-22T17:00:00Z"


def inputs():
    rows=[f"136799-{i+1},Player{i},{POS[i]},{ROSTER[i]},5000,DAL,DAL@NYG,{('O' if i==9 else '')}"
          for i in range(10)]
    csv=HEAD+"\n"+"\n".join(rows)
    projections=[{"player_id":f"136799-{i+1}","projection_fd":10+i,"asof_utc":TIME} for i in range(9)]
    candidate={"candidate_id":"entered","contest_id":"136799","slate_date":"2026-11-22",
               "created_utc":TIME,"slots":dict(zip(SLOTS,[f"136799-{i+1}" for i in range(9)]))}
    kw={"contest_id":"136799","slate_date":"2026-11-22","source_version":"DAILY",
        "cutoff_utc":TIME}
    return csv,projections,[candidate],kw


class NFLPipelineTests(unittest.TestCase):
    def test_uncertified_without_source_provenance(self):
        csv, projections, candidates, kw = inputs()
        result = run_nfl_prelock_pipeline(csv, projections, candidates, **kw)
        self.assertTrue(result["ready"])
        self.assertFalse(result["certified"])
        self.assertEqual(len(result["unverified_projection_ids"]), 9)
        self.assertEqual(len(result["uncertain_status_ids"]), 9)

    def test_certified_with_traceable_projections_and_status(self):
        csv, projections, candidates, kw = inputs()
        csv = csv.replace("DAL@NYG,\n", "DAL@NYG,PROBABLE\n")
        for p in projections:
            p["source"] = "Archived independent provider"
            p["source_version"] = "v1"
        for p in projections:
            p["source_record_id"] = "record-" + p["player_id"]
        evidence = [{"player_id": p["player_id"], "status": "active",
                     "official": True, "source": "Official team report",
                     "source_record_id": "status-" + p["player_id"],
                     "observed_at": TIME} for p in projections]
        result = run_nfl_prelock_pipeline(csv, projections, candidates,
                                          official_status_evidence=evidence, **kw)
        self.assertTrue(result["ready"])
        self.assertTrue(result["certified"])

    def test_official_inactive_conflict_blocks_rankings(self):
        csv, projections, candidates, kw = inputs()
        evidence = [{"player_id": "136799-1", "status": "inactive",
                     "official": True, "source": "Official inactive list",
                     "source_record_id": "official-1", "observed_at": TIME}]
        result = run_nfl_prelock_pipeline(
            csv, projections, candidates, official_status_evidence=evidence, **kw)
        self.assertFalse(result["ready"])
        self.assertEqual(result["rankings"], [])
        self.assertEqual(result["officially_out_conflict_ids"], ["136799-1"])

    def test_future_inactive_report_does_not_change_historical_rankings(self):
        csv, projections, candidates, kw = inputs()
        evidence = [{"player_id": "136799-1", "status": "inactive",
                     "official": True, "source": "Official inactive list",
                     "source_record_id": "official-late",
                     "observed_at": "2026-11-22T18:00:00Z"}]
        result = run_nfl_prelock_pipeline(
            csv, projections, candidates, official_status_evidence=evidence, **kw)
        self.assertTrue(result["ready"])
        self.assertFalse(result["certified"])
        self.assertEqual(result["officially_out_conflict_ids"], [])

    def test_duplicate_official_evidence_rejected(self):
        csv, projections, candidates, kw = inputs()
        entry = {"player_id": "136799-1", "status": "active"}
        with self.assertRaises(ValueError):
            run_nfl_prelock_pipeline(
                csv, projections, candidates,
                official_status_evidence=[entry, entry], **kw)

    def test_missing_official_source_is_not_certified(self):
        csv, projections, candidates, kw = inputs()
        for p in projections:
            p.update(source="Provider", source_version="v1",
                     source_record_id="record-" + p["player_id"])
        evidence = [{"player_id": p["player_id"], "status": "active",
                     "official": True, "observed_at": TIME}
                    for p in projections]
        result = run_nfl_prelock_pipeline(
            csv, projections, candidates, official_status_evidence=evidence, **kw)
        self.assertTrue(result["ready"])
        self.assertFalse(result["certified"])

    def test_end_to_end(self):
        csv,projections,candidates,kw=inputs()
        result=run_nfl_prelock_pipeline(csv,projections,candidates,**kw)
        self.assertTrue(result["ready"])
        self.assertEqual(result["contest_players"],10)
        self.assertEqual(result["excluded_out_ids"],["136799-10"])
        self.assertEqual(result["eligible_players"],9)
        self.assertEqual(result["rankings"][0]["projected_fd"],126)

    def test_missing_projection_blocks_rankings(self):
        csv,projections,candidates,kw=inputs()
        result=run_nfl_prelock_pipeline(csv,projections[:-1],candidates,**kw)
        self.assertFalse(result["ready"])
        self.assertEqual(result["rankings"],[])
        self.assertEqual(result["missing_projection_ids"],["136799-9"])

    def test_missing_projection_on_out_player_not_required(self):
        csv,projections,candidates,kw=inputs()
        self.assertTrue(run_nfl_prelock_pipeline(csv,projections,candidates,**kw)["ready"])

    def test_postcutoff_projection_rejected(self):
        csv,projections,candidates,kw=inputs()
        projections[0]["asof_utc"]="2026-11-22T18:00:00Z"
        with self.assertRaises(ValueError):run_nfl_prelock_pipeline(csv,projections,candidates,**kw)

    def test_out_player_in_candidate_rejected(self):
        csv,projections,candidates,kw=inputs()
        candidates[0]["slots"]["QB"]="136799-10"
        with self.assertRaises(ValueError):run_nfl_prelock_pipeline(csv,projections,candidates,**kw)

    def test_mismatched_contest_rejected(self):
        csv,projections,candidates,kw=inputs()
        kw["contest_id"]="999999"
        with self.assertRaises(ValueError):run_nfl_prelock_pipeline(csv,projections,candidates,**kw)

    def test_salary_violation_rejected(self):
        csv,projections,candidates,kw=inputs()
        csv=csv.replace("5000,DAL", "9000,DAL")
        with self.assertRaises(ValueError):run_nfl_prelock_pipeline(csv,projections,candidates,**kw)


if __name__=="__main__":
    unittest.main()
