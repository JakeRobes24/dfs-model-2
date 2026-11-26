import unittest
from nfl_daily_audit import audit_nfl_daily, read_daily
from test_nfl_contest_import import sample

HEADER="player,team,gameInfo,salary,value,completionsAttempts,passingYards,passingTouchdowns,interceptionsThrown,rushingAttempts,rushingYards,rushingTouchdowns,receptions,targets,receivingYards,receivingTouchdowns,fantasy,positionRank,overallRank,opponentDefensiveRank"
OFF="Dak Prescott,Dallas Cowboys,DAL @ NYG,$8200,2.5,20/32,250,2,1,2,10,0,0,0,0,0,20.8,,,"
DST="Buffalo D/ST,Buffalo Bills,BUF @ MIA,$4900,1,20,300,2,1,0.2,0.1,4.9,,"
K="Trey Smack,Green Bay Packers,GB @ LA,N/A,N/A,2,2,2,1,0,0.5,0.5,0.5,0.1,7.6,,"
def export(*rows):
    return HEADER+"\n"+"\n".join(rows)

class NFLDailyAuditTests(unittest.TestCase):
    def test_full_pool_missing_preserved_and_dst_not_misread(self):
        result=audit_nfl_daily(sample(),export(OFF,DST),contest_id="136799")
        self.assertEqual(result["contest_players"],3)
        self.assertEqual(result["matched"],2)
        self.assertEqual(result["eligible_header_scores"],1)
        self.assertIsNone(result["players"][1]["projection_fd"])
        self.assertEqual(result["players"][2]["unlabeled_fd_candidate"],4.9)
        self.assertIsNone(result["players"][2]["projection_fd"])
        self.assertFalse(result["certified"])

    def test_kicker_layout_and_la_alias(self):
        r=read_daily(export(K))[0]
        self.assertEqual(r["game"],"GB@LAR")
        self.assertEqual(r["layout"],"kicker_unlabeled")
        self.assertEqual(r["unlabeled_fd_candidate"],7.6)
        self.assertIsNone(r["projection_fd"])

    def test_wrong_team_not_joined(self):
        wrong=OFF.replace("Dallas Cowboys","New York Giants")
        r=audit_nfl_daily(sample(),export(wrong),contest_id="136799")
        self.assertEqual(r["matched"],0)

    def test_duplicate_source_not_joined(self):
        r=audit_nfl_daily(sample(),export(OFF,OFF),contest_id="136799")
        self.assertIn("ambiguous_identity",r["players"][0]["issues"])
        self.assertIsNone(r["players"][0]["projection_fd"])

    def test_salary_mismatch_preserves_contest(self):
        r=audit_nfl_daily(sample(),export(OFF.replace("$8200","$9000")),contest_id="136799")
        self.assertEqual(r["players"][0]["salary"],8200)
        self.assertIn("daily_salary_mismatch",r["players"][0]["issues"])

    def test_zero_and_missing_are_distinct(self):
        r=audit_nfl_daily(sample(),export(OFF.replace("20.8,,,","0,,,")),contest_id="136799")
        self.assertEqual(r["players"][0]["projection_fd"],0)
        self.assertIsNone(r["players"][1]["projection_fd"])

    def test_header_schema_drift_rejected(self):
        with self.assertRaises(ValueError):
            read_daily(export(OFF).replace("fantasy,","unknown,"))

    def test_known_id_alias(self):
        contest="Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator\n137123-91626,James Cook III,RB,RB/FLEX,8700,BUF,KC@BUF,"
        daily=OFF.replace("Dak Prescott,Dallas Cowboys,DAL @ NYG,$8200","James Cook,Buffalo Bills,KC @ BUF,$8700")
        self.assertEqual(audit_nfl_daily(contest,export(daily),contest_id="137123")["matched"],1)

    def test_no_kicker_score_on_offensive_position(self):
        c="Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator\n137104-1,Trey Smack,WR,WR/FLEX,6200,GB,GB@LAR,"
        r=audit_nfl_daily(c,export(K),contest_id="137104")
        self.assertIn("position_layout_mismatch",r["players"][0]["issues"])
        self.assertIsNone(r["players"][0]["unlabeled_fd_candidate"])
