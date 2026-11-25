import unittest
import ast
from pathlib import Path
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
    def test_streamlit_guard_keeps_mean_sensitivity_out_of_gpp_mode(self):
        source=Path(__file__).with_name("site_ui.py").read_text(encoding="utf-8")
        tree=ast.parse(source)
        guards=[node for node in ast.walk(tree) if isinstance(node,ast.If)
                and isinstance(node.test,ast.Compare)
                and isinstance(node.test.left,ast.Name)
                and node.test.left.id=="objective"
                and any(isinstance(op,ast.NotEq) for op in node.test.ops)
                and any(isinstance(c,ast.Constant) and c.value=="adjusted_fd_points"
                        for c in node.test.comparators)]
        self.assertTrue(guards,"Missing objective-specific Streamlit guard")
        self.assertTrue(any(any(isinstance(n,ast.Call)
                                 and isinstance(n.func,ast.Name)
                                 and n.func.id=="rank_fragility"
                                 for branch in guard.orelse for n in ast.walk(branch))
                            for guard in guards),"Sensitivity call must be confined to mean-FD objective")
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
    def test_optimizer_rounding_accepted_but_baseline_uses_unrounded_pool(self):
        self.pool.loc[9,"adjusted_fd_points"]=30.004965034965035
        self.lineups["adjusted_fd_points"]=self.lineups.fanduel_id.map(
            self.pool.set_index("fanduel_id").adjusted_fd_points).round(2)
        result=rank_fragility(self.pool,self.lineups)
        self.assertEqual(result["baseline_leader"],"2")
        self.lineups.loc[self.lineups.fanduel_id.eq("9"),"adjusted_fd_points"]=30.01
        with self.assertRaisesRegex(ValueError,"projection mismatch"):
            rank_fragility(self.pool,self.lineups)

    def test_nonfinite_pool_points_rejected(self):
        self.pool.loc[9,"adjusted_fd_points"]=float("nan")
        with self.assertRaisesRegex(ValueError,"projection mismatch"):
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
    def test_capped_selection_is_deterministic(self):
        first=rank_fragility(self.pool,self.lineups,max_players=1)
        second=rank_fragility(self.pool.sample(frac=1,random_state=17),
                             self.lineups.sample(frac=1,random_state=23),max_players=1)
        self.assertEqual(first["rows"],second["rows"])
        self.assertEqual(first["tested_differential_players"],1)
    def test_invalid_cap(self):
        with self.assertRaises(ValueError):
            rank_fragility(self.pool,self.lineups,max_players=0)
    def test_invalid_differential_minutes_fails_closed(self):
        self.pool.loc[9,"adjusted_minutes"]=0
        with self.assertRaisesRegex(ValueError,"Invalid minutes"):
            rank_fragility(self.pool,self.lineups)
    def test_nonnumeric_differential_minutes_fails_closed(self):
        self.pool["adjusted_minutes"]=self.pool["adjusted_minutes"].astype(object)
        self.pool.loc[9,"adjusted_minutes"]="unknown"
        with self.assertRaisesRegex(ValueError,"Invalid minutes"):
            rank_fragility(self.pool,self.lineups)
    def test_negative_differential_points_fails_closed(self):
        self.pool.loc[9,"adjusted_fd_points"]=-1
        self.lineups.loc[self.lineups.fanduel_id.eq("9"),"adjusted_fd_points"]=-1
        with self.assertRaisesRegex(ValueError,"Invalid minutes"):
            rank_fragility(self.pool,self.lineups)
    def test_missing_pool_id_fails_closed(self):
        self.pool.loc[0,"fanduel_id"]=None
        with self.assertRaisesRegex(ValueError,"Missing contest player IDs"):
            rank_fragility(self.pool,self.lineups)
    def test_missing_lineup_id_fails_closed(self):
        self.lineups.loc[0,"fanduel_id"]=None
        with self.assertRaisesRegex(ValueError,"Missing contest player IDs"):
            rank_fragility(self.pool,self.lineups)
    def test_nonnumeric_candidate_projection_fails_closed(self):
        self.lineups["adjusted_fd_points"]=self.lineups["adjusted_fd_points"].astype(object)
        self.lineups.loc[0,"adjusted_fd_points"]="unknown"
        with self.assertRaisesRegex(ValueError,"Non-numeric"):
            rank_fragility(self.pool,self.lineups)
    def test_invalid_spread_type_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Minute spread"):
            rank_fragility(self.pool,self.lineups,minute_spread="two")
    def test_missing_lineup_label_fails_closed(self):
        self.lineups.loc[0,"lineup"]=None
        with self.assertRaisesRegex(ValueError,"Missing lineup labels"):
            rank_fragility(self.pool,self.lineups)
    def test_blank_lineup_label_fails_closed(self):
        self.lineups["lineup"]=self.lineups["lineup"].astype(object)
        self.lineups.loc[0,"lineup"]=" "
        with self.assertRaisesRegex(ValueError,"Missing lineup labels"):
            rank_fragility(self.pool,self.lineups)
    def test_ambiguous_lineup_labels_fails_closed(self):
        self.lineups["lineup"]=self.lineups["lineup"].astype(object)
        self.lineups.loc[0,"lineup"]="1"
        with self.assertRaisesRegex(ValueError,"Ambiguous lineup labels"):
            rank_fragility(self.pool,self.lineups)
    def test_numeric_string_projections_are_summed_numerically(self):
        self.pool["adjusted_fd_points"]=self.pool.adjusted_fd_points.astype(str)
        self.lineups["adjusted_fd_points"]=self.lineups.adjusted_fd_points.astype(str)
        result=rank_fragility(self.pool,self.lineups)
        self.assertEqual(result["baseline_leader"],"2")
        self.assertTrue(result["fragile"])
    def test_shared_player_invalid_minutes_fails_closed(self):
        self.lineups.loc[self.lineups.fanduel_id.eq("9"),"fanduel_id"]="0"
        self.lineups.loc[self.lineups.lineup.eq(2) & self.lineups.fanduel_id.eq("0"),"adjusted_fd_points"]=30.0
        self.pool.loc[0,"adjusted_minutes"]=0
        with self.assertRaisesRegex(ValueError,"Invalid minutes"):
            rank_fragility(self.pool,self.lineups)
    def test_single_candidate_invalid_minutes_fails_closed(self):
        self.pool.loc[0,"adjusted_minutes"]=0
        with self.assertRaisesRegex(ValueError,"Invalid minutes"):
            rank_fragility(self.pool,self.lineups[self.lineups.lineup==1])
    def test_one_lineup(self):
        result=rank_fragility(self.pool,self.lineups[self.lineups.lineup==1])
        self.assertFalse(result["fragile"])

if __name__=="__main__":
    unittest.main()
