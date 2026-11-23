import unittest
import pandas as pd
from nba_live_prelock_fragility import rank_fragility

class LiveFragilityTests(unittest.TestCase):
    def setUp(self):
        self.pool=pd.DataFrame([
            {"fanduel_id":str(i),"fanduel_name":f"P{i}",
             "adjusted_fd_points":30.0,"adjusted_minutes":30.0}
            for i in range(18)])
        self.pool.loc[9,"adjusted_fd_points"]=31.0
        self.lineups=pd.DataFrame([
            {"lineup":lineup,"fanduel_id":str(i),
             "adjusted_fd_points":float(self.pool.loc[i,"adjusted_fd_points"])}
            for lineup,indices in [(1,range(9)),(2,range(9,18))]
            for i in indices])
    def test_detects_flip(self):
        result=rank_fragility(self.pool,self.lineups,minute_spread=2)
        self.assertTrue(result["fragile"])
        self.assertEqual(result["baseline_leader"],"2")
    def test_zero_spread(self):
        with self.assertRaises(ValueError):
            rank_fragility(self.pool,self.lineups,minute_spread=0)
    def test_duplicate_id(self):
        self.pool=pd.concat([self.pool,self.pool.iloc[[0]]],ignore_index=True)
        with self.assertRaises(ValueError):
            rank_fragility(self.pool,self.lineups)
    def test_bad_projection(self):
        self.lineups.loc[0,"adjusted_fd_points"]=99
        with self.assertRaises(ValueError):
            rank_fragility(self.pool,self.lineups)
    def test_missing_player(self):
        self.lineups.loc[0,"fanduel_id"]="missing"
        with self.assertRaises(ValueError):
            rank_fragility(self.pool,self.lineups)
    def test_all_differential_players_checked(self):
        result=rank_fragility(self.pool,self.lineups)
        self.assertEqual(result["tested_differential_players"],18)
        self.assertTrue(result["coverage_complete"])
    def test_explicit_cap_discloses_partial_coverage(self):
        result=rank_fragility(self.pool,self.lineups,max_players=2)
        self.assertEqual(result["tested_differential_players"],2)
        self.assertFalse(result["coverage_complete"])
    def test_invalid_cap(self):
        with self.assertRaises(ValueError):
            rank_fragility(self.pool,self.lineups,max_players=0)
    def test_invalid_differential_minutes_fails_closed(self):
        self.pool.loc[9,"adjusted_minutes"]=0
        with self.assertRaisesRegex(ValueError,"Invalid minutes"):
            rank_fragility(self.pool,self.lineups)
    def test_one_lineup(self):
        result=rank_fragility(self.pool,self.lineups[self.lineups.lineup==1])
        self.assertFalse(result["fragile"])

if __name__=="__main__":
    unittest.main()
