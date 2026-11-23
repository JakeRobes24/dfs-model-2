import csv
import io
import unittest
from nba_prelock_robustness import compare_minutes_bounds

def to_csv(rows):
    f=io.StringIO()
    w=csv.DictWriter(f,fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
    return f.getvalue()

class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.pool=[]
        self.lineups=[]
        for i in range(18):
            self.pool.append({"id":str(i),"consensus_scenario_minutes":"28",
                              "consensus_scenario_fd":"28"})
        for name,indices in (("1",range(9)),("2",range(9,18))):
            for i in indices:
                self.lineups.append({"lineup":name,"player_id":str(i),"scenario_fd":"28"})
    def run_audit(self,low=27,high=33):
        return compare_minutes_bounds(to_csv(self.pool),to_csv(self.lineups),"9",low,high)
    def test_winner_changes(self):
        result=self.run_audit()
        self.assertTrue(result["winner_changes"])
        self.assertEqual(result["bounds"][0]["winner"],"1")
        self.assertEqual(result["bounds"][1]["winner"],"2")
    def test_crossing(self):
        self.assertAlmostEqual(self.run_audit()["crossings"][0]["minutes"],28)
    def test_invalid_bounds(self):
        with self.assertRaises(ValueError):self.run_audit(33,27)
    def test_duplicate_id(self):
        self.pool.append(dict(self.pool[0]))
        with self.assertRaises(ValueError):self.run_audit()
    def test_missing_id(self):
        self.lineups[0]["player_id"]="999"
        with self.assertRaises(ValueError):self.run_audit()
    def test_projection_mismatch(self):
        self.lineups[0]["scenario_fd"]="100"
        with self.assertRaises(ValueError):self.run_audit()
    def test_duplicate_lineup_player(self):
        self.lineups[0]["player_id"]=self.lineups[1]["player_id"]
        with self.assertRaises(ValueError):self.run_audit()
if __name__=="__main__":unittest.main()
