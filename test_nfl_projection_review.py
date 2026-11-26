import unittest
from copy import deepcopy
from nfl_projection_review import review_nfl_projections

P="137123-1"
AUDIT={"contest_id":"137123","contest_sha256":"a","daily_sha256":"b","players":[
    {"player_id":P,"player":"Example","team":"BUF","game":"KC@BUF","status":"unknown",
     "projection_fd":None,"unlabeled_fd_candidate":5.0}]}
TIME="2026-11-26T16:00:00Z"
def evidence(family="one",score=5.2,**kw):
    return dict({"player_id":P,"contest_id":"137123","slate_date":"2026-11-26",
                 "team":"BUF","game":"KC@BUF","scoring":"FanDuel","source":family,
                 "source_family":family,"source_record_id":"row1",
                 "independence_reviewed":True,"asof_utc":"2026-11-26T14:00:00Z",
                 "observed_at":"2026-11-26T15:00:00Z","projection_fd":score},**kw)
def review(records,audit=AUDIT):
    return review_nfl_projections(audit,records,cutoff_utc=TIME,slate_date="2026-11-26")

class ProjectionReviewTests(unittest.TestCase):
    def test_two_independent_families_propose_not_replace(self):
        a=deepcopy(AUDIT)
        r=review([evidence(),evidence("two",5.8)],a)
        self.assertEqual(r["rows"][0]["decision"],"corroborated_gap_review")
        self.assertEqual(r["rows"][0]["review_consensus_fd"],5.5)
        self.assertIsNone(r["rows"][0]["daily_fd"])
        self.assertEqual(a,AUDIT)
        self.assertFalse(r["certified"])
    def test_duplicate_family_not_consensus(self):
        r=review([evidence(),evidence("ONE",source_record_id="row2")])
        self.assertEqual(r["rows"][0]["independent_family_count"],1)
        self.assertEqual(r["rows"][0]["decision"],"missing_requires_research")
    def test_family_conflict_rejected(self):
        r=review([evidence(),evidence(score=9,source_record_id="row2"),evidence("two")])
        self.assertEqual(r["rows"][0]["decision"],"source_disagreement")
    def test_disagreement_not_averaged(self):
        r=review([evidence(),evidence("two",12)])
        self.assertIsNone(r["rows"][0]["review_consensus_fd"])
    def test_future_stale_and_undated_rejected(self):
        r=review([evidence(observed_at="2026-11-26T17:00:00Z"),
                  evidence(asof_utc="2026-11-24T15:00:00Z"),evidence(asof_utc="")])
        self.assertEqual(len(r["rejected_evidence"]),3)
    def test_wrong_team_game_date_scoring_and_contest_rejected(self):
        r=review([evidence(team="KC"),evidence(game="BUF@KC"),evidence(slate_date="2026-11-25"),
                  evidence(scoring="DraftKings"),evidence(contest_id="137104")])
        self.assertEqual(len(r["rejected_evidence"]),5)
    def test_unverified_independence_and_daily_rejected(self):
        r=review([evidence(independence_reviewed=False),evidence("DAILY")])
        self.assertEqual(len(r["rejected_evidence"]),2)
    def test_duplicate_record_not_counted(self):
        r=review([evidence(),evidence()])
        self.assertEqual(r["rejected_evidence"][0]["reason"],"duplicate_record")
    def test_daily_score_preserved_on_disagreement(self):
        a=deepcopy(AUDIT);a["players"][0]["projection_fd"]=15
        r=review([evidence(),evidence("two")],a)
        self.assertEqual(r["rows"][0]["daily_fd"],15)
        self.assertEqual(r["rows"][0]["decision"],"baseline_disagreement")
    def test_out_player_never_suggested(self):
        a=deepcopy(AUDIT);a["players"][0]["status"]="out"
        r=review([evidence(),evidence("two")],a)
        self.assertEqual(r["rows"][0]["decision"],"contest_out")
    def test_invalid_number_and_unknown_player(self):
        r=review([evidence(score=float("nan")),evidence(player_id="not-in-contest")])
        self.assertEqual(len(r["rejected_evidence"]),2)

    def test_conflicting_duplicate_quarantines_family_in_both_orders(self):
        records=[evidence(),evidence(score=9),evidence("two"),evidence("three")]
        for submitted in (records,list(reversed(records))):
            r=review(submitted)
            row=r["rows"][0]
            self.assertEqual(row["decision"],"source_disagreement")
            self.assertEqual(row["conflicting_families"],["one"])
            self.assertIsNone(row["review_consensus_fd"])
            self.assertNotIn("one",row["family_scores"])
            self.assertEqual(sum(e["reason"]=="conflicting_duplicate_record" for e in r["rejected_evidence"]),2)

    def test_same_source_cannot_vote_as_two_families(self):
        r=review([evidence(),evidence("two",source=" ONE ")])
        self.assertIsNone(r["rows"][0]["review_consensus_fd"])
        self.assertEqual(r["rows"][0]["conflicting_families"],["one","two"])
        self.assertEqual(r["rows"][0]["independent_family_count"],0)

    def test_inconsistent_source_family_detected_across_players(self):
        a=deepcopy(AUDIT)
        p2="137123-2"
        a["players"].append(dict(a["players"][0],player_id=p2))
        r=review([evidence(),evidence("two",source="one",player_id=p2)],a)
        self.assertTrue(all(row["decision"]=="source_disagreement" for row in r["rows"]))
        self.assertTrue(all(row["review_consensus_fd"] is None for row in r["rows"]))

    def test_same_record_changed_publication_not_silently_accepted(self):
        r=review([evidence(),evidence(asof_utc="2026-11-26T14:30:00Z"),evidence("two")])
        self.assertEqual(r["rows"][0]["decision"],"source_disagreement")
        self.assertIsNone(r["rows"][0]["review_consensus_fd"])

    def test_same_record_reobserved_is_one_vote(self):
        r=review([evidence(observed_at="2026-11-26T15:30:00Z"),
                  evidence(observed_at="2026-11-26T15:00:00Z"),evidence("two")])
        self.assertEqual(r["rows"][0]["decision"],"corroborated_gap_review")
        self.assertEqual(r["rows"][0]["independent_family_count"],2)
        self.assertEqual(r["rows"][0]["accepted_source_records"][0]["observed_at"],"2026-11-26T15:00:00Z")

    def test_unavailable_status_suppresses_consensus(self):
        for status in ("out","inactive","suspended","IR"):
            a=deepcopy(AUDIT)
            a["players"][0]["status"]=status
            r=review([evidence(),evidence("two")],a)
            self.assertEqual(r["rows"][0]["decision"],"contest_out")
            self.assertIsNone(r["rows"][0]["review_consensus_fd"])
