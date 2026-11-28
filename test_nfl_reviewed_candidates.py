import unittest
from hashlib import sha256
from nfl_reviewed_candidates import compare_reviewed_nfl

HEAD="Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator"
DAILY="player,team,gameInfo,salary,value,completionsAttempts,passingYards,passingTouchdowns,interceptionsThrown,rushingAttempts,rushingYards,rushingTouchdowns,receptions,targets,receivingYards,receivingTouchdowns,fantasy,positionRank,overallRank,opponentDefensiveRank"
TIME="2026-11-26T16:00:00Z"
DATE="2026-11-26"
def fixture(single=False):
    pos=["QB","RB","WR","TE","RB","WR"] if single else ["QB","RB","RB","WR","WR","WR","TE","RB","D"]
    rows=[]; daily=[]; evidence=[]
    for i,p in enumerate(pos):
        t="BUF" if i%2 else "KC"
        name=f"Player {i}" if p!="D" else "Kansas City Chiefs"
        r="MVP - 1.5X Points/AnyFLEX" if single else ("DEF" if p=="D" else p+"/FLEX" if p in ("RB","WR","TE") else p)
        pid=f"137123-{i+1}"
        rows.append(f"{pid},{name},{p},{r},5000,{t},KC@BUF,"+(",7500" if single else ""))
        if p!="D":
            daily.append(f"{name},{t},KC@BUF,5000,2,0/0,0,0,0,0,0,0,0,0,0,0,10,,,")
        else:
            for family in ("a","b"):
                evidence.append(dict(player_id=pid,contest_id="137123",slate_date=DATE,team=t,game="KC@BUF",
                                     scoring="FanDuel",source=family,source_family=family,source_record_id="record",
                                     independence_reviewed=True,asof_utc=TIME,observed_at=TIME,projection_fd=10))
    c=(HEAD+(",MVP 1.5x Salary" if single else "")+"\n"+"\n".join(rows)).encode()
    d=(DAILY+"\n"+"\n".join(daily)).encode()
    ids=[f"137123-{i+1}" for i in range(len(pos))]
    candidate=dict(candidate_id="A",contest_id="137123",slate_date=DATE,created_utc=TIME)
    if single:
        candidate.update(roster_ids=ids,mvp=ids[0])
    else:
        candidate.update(slots=dict(zip(["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DEF"],ids)))
    kw=dict(contest_id="137123",single_game=single,slate_date=DATE,cutoff_utc=TIME,
            daily_capture=dict(daily_sha256=sha256(d).hexdigest(),slate_date=DATE,contest_id="137123",
                               source_record_id="fixture",reviewed=True,observed_at=TIME),
            evidence=evidence,candidates=[candidate],salary_cap=60000)
    return c,d,kw

class ReviewedCandidateTests(unittest.TestCase):
    def test_full_classic_with_independent_gap(self):
        c,d,kw=fixture()
        r=compare_reviewed_nfl(c,d,**kw)
        self.assertTrue(r["ready"])
        self.assertFalse(r["certified"])
        self.assertEqual(r["rankings"][0]["projected_fd"],90)
        self.assertEqual(r["accepted_players"][-1]["score_origin"],"experimental_independent_consensus")
    def test_missing_full_pool_blocks(self):
        c,d,kw=fixture();kw["evidence"]=[]
        r=compare_reviewed_nfl(c,d,**kw)
        self.assertFalse(r["ready"])
        self.assertEqual(r["rankings"],[])
    def test_single_game_mvp_and_salary(self):
        c,d,kw=fixture(True)
        r=compare_reviewed_nfl(c,d,**kw)
        self.assertEqual(r["rankings"][0]["salary"],32500)
        self.assertEqual(r["rankings"][0]["projected_fd"],65)
    def test_single_game_cap(self):
        c,d,kw=fixture(True);kw["salary_cap"]=32000
        with self.assertRaises(ValueError):compare_reviewed_nfl(c,d,**kw)
    def test_wrong_capture_hash(self):
        c,d,kw=fixture();kw["daily_capture"]["daily_sha256"]="wrong"
        with self.assertRaises(ValueError):compare_reviewed_nfl(c,d,**kw)
    def test_future_capture(self):
        c,d,kw=fixture();kw["daily_capture"]["observed_at"]="2026-11-26T17:00:00Z"
        with self.assertRaises(ValueError):compare_reviewed_nfl(c,d,**kw)
    def test_future_candidate(self):
        c,d,kw=fixture();kw["candidates"][0]["created_utc"]="2026-11-26T17:00:00Z"
        with self.assertRaises(ValueError):compare_reviewed_nfl(c,d,**kw)
    def test_duplicate_candidate(self):
        c,d,kw=fixture();kw["candidates"]*=2
        with self.assertRaises(ValueError):compare_reviewed_nfl(c,d,**kw)
    def test_conflicting_sources_block(self):
        c,d,kw=fixture();kw["evidence"][1]["projection_fd"]=30
        self.assertFalse(compare_reviewed_nfl(c,d,**kw)["ready"])
    def test_actual_evidence_observation_times_preserved(self):
        c,d,kw=fixture()
        kw["daily_capture"]["observed_at"]="2026-11-26T14:00:00Z"
        for record in kw["evidence"]:
            record.update(asof_utc="2026-11-26T14:00:00Z",observed_at="2026-11-26T15:00:00Z")
        r=compare_reviewed_nfl(c,d,**kw)
        self.assertEqual(r["accepted_players"][0]["asof_utc"],"2026-11-26T14:00:00Z")
        self.assertEqual(r["accepted_players"][-1]["asof_utc"],"2026-11-26T15:00:00Z")
        self.assertEqual(len(r["source_review"]["rows"][-1]["accepted_source_records"]),2)
    def test_capture_not_reviewed(self):
        c,d,kw=fixture();kw["daily_capture"]["reviewed"]=False
        with self.assertRaises(ValueError):compare_reviewed_nfl(c,d,**kw)

    def test_conflicting_daily_salary_blocks_even_with_finite_projection(self):
        c,d,kw=fixture(True)
        d=d.replace(b"Player 0,KC,KC@BUF,5000,",b"Player 0,KC,KC@BUF,5100,",1)
        kw["daily_capture"]["daily_sha256"]=sha256(d).hexdigest()
        report=compare_reviewed_nfl(c,d,**kw)
        self.assertFalse(report["ready"])
        self.assertEqual(report["rankings"],[])
        self.assertEqual(report["unresolved"][0]["issues"],["daily_salary_mismatch"])

    def test_ambiguous_daily_identity_blocks_even_with_independent_evidence(self):
        c,d,kw=fixture()
        d+=b"\n"+d.splitlines()[1]
        kw["daily_capture"]["daily_sha256"]=sha256(d).hexdigest()
        for family in ("a","b"):
            kw["evidence"].append(dict(kw["evidence"][0],player_id="137123-1",
                                       source=family,source_family=family))
        report=compare_reviewed_nfl(c,d,**kw)
        self.assertFalse(report["ready"])
        self.assertIn("ambiguous_identity",report["unresolved"][0]["issues"])

    def test_classic_and_single_game_use_same_score_bounds(self):
        for single in (False,True):
            c,d,kw=fixture(single)
            d=d.replace(b",10,,,",b",151,,,",1)
            kw["daily_capture"]["daily_sha256"]=sha256(d).hexdigest()
            report=compare_reviewed_nfl(c,d,**kw)
            self.assertFalse(report["ready"])
            self.assertEqual(report["unresolved"][0]["reason"],"score_outside_review_bounds")

    def test_outside_bounds_consensus_cannot_fill_missing_score(self):
        c,d,kw=fixture()
        for record in kw["evidence"]:
            record["projection_fd"]=151
        report=compare_reviewed_nfl(c,d,**kw)
        self.assertFalse(report["ready"])
        self.assertEqual(report["unresolved"][0]["reason"],"score_outside_review_bounds")

    def test_negative_finite_score_preserved(self):
        c,d,kw=fixture(True)
        d=d.replace(b",10,,,",b",-1,,,",1)
        kw["daily_capture"]["daily_sha256"]=sha256(d).hexdigest()
        report=compare_reviewed_nfl(c,d,**kw)
        self.assertTrue(report["ready"])
        self.assertEqual(report["accepted_players"][0]["projection_fd"],-1)
        self.assertEqual(report["rankings"][0]["projected_fd"],48.5)
