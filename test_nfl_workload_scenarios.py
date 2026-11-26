import unittest
from nfl_workload_scenarios import backfield_scenarios, compare_mvp_assignments

def pool():
    return [dict(player_id=str(i),team="LAR" if i<4 else "GB",game="GB@LAR",
                 positions=["RB"] if i<2 else ["WR"],status="unknown",salary=8000,
                 mvp_salary=12000,roster_eligibility=["MVP - 1.5X POINTS","ANYFLEX"])
            for i in range(6)]

def pair():
    return [dict(player_id="0",projection_fd=16.6,carries=9.43,rushing_yards=42.16,rushing_td=.22),
            dict(player_id="1",projection_fd=20.6,carries=16.86,rushing_yards=74.86,rushing_td=.53)]

class NFLWorkloadTests(unittest.TestCase):
    def test_share_and_volume_conserved_and_receiving_unchanged(self):
        p=pair()
        r=backfield_scenarios(pool(),p)
        self.assertEqual(len(r["scenarios"]),9)
        self.assertFalse(r["provenance_checked"])
        for s in r["scenarios"]:
            self.assertAlmostEqual(sum(x["carries"] for x in s["players"]),s["pair_carries"])
            for actual,original in zip(s["players"],p):
                self.assertAlmostEqual(actual["projection_fd"]-original["projection_fd"],
                    (actual["carries"]-original["carries"])*actual["rush_fd_per_carry"])
        self.assertAlmostEqual(r["baseline_first_share"],9.43/26.29)

    def test_reject_unverified_cutoff_and_wrong_team(self):
        with self.assertRaises(ValueError):
            backfield_scenarios(pool(),pair(),cutoff_utc="2026-11-25T23:00:00Z")
        c=pool()
        c[0]["team"]="GB"
        with self.assertRaises(ValueError):
            backfield_scenarios(c,pair())
        p=pair()
        p[0]["rushing_yards"]=None
        with self.assertRaises(ValueError):
            backfield_scenarios(pool(),p)

    def test_mvp_comparison_uses_exact_salary_and_multiplier(self):
        c=pool()
        c[0].update(salary=16000,mvp_salary=24000)
        ids=[p["player_id"] for p in c]
        points={pid:float(30-int(pid)) for pid in ids}
        r=compare_mvp_assignments(c,ids,points,salary_cap=60000)
        self.assertEqual(len(r),5)
        self.assertEqual(r[0]["mvp"],"1")
        self.assertEqual(r[0]["salary"],60000)
        self.assertAlmostEqual(r[0]["projected_fd"],sum(points.values())+.5*points["1"])
        with self.assertRaises(ValueError):
            compare_mvp_assignments(c,ids,{},salary_cap=60000)

if __name__=="__main__":
    unittest.main()


class NFLTeamVolumeTests(unittest.TestCase):
    def test_missing_and_out_conflict_cannot_certify_budget(self):
        from nfl_workload_scenarios import team_workload_review
        c=pool()
        c[3]["status"]="out"
        records=[dict(player_id="0",pass_attempts=0,targets=6,carries=12),
                 dict(player_id="1",pass_attempts=0,targets=5,carries=10),
                 dict(player_id="3",pass_attempts=0,targets=1,carries=0)]
        r=team_workload_review(c,records,team="LAR",game="GB@LAR")
        self.assertEqual(r["missing_ids"],["2"])
        self.assertEqual(r["out_workload_conflicts"],["3"])
        self.assertFalse(r["receiving_budget_supported"])
        self.assertEqual(r["matched_totals"]["targets"],11)
        c[2]["positions"]=["QB"]
        records=[dict(x,targets=0) if x["player_id"]=="3" else x for x in records]
        records.append(dict(player_id="2",pass_attempts=12,targets=0,carries=1))
        r=team_workload_review(c,records,team="LAR",game="GB@LAR")
        self.assertTrue(r["receiving_budget_supported"])
        self.assertEqual(r["attempt_minus_target_gap"],1)
        self.assertFalse(team_workload_review(c,records,team="LAR",game="GB@LAR",
                         cutoff_utc="2026-11-25T23:00:00Z")["receiving_budget_supported"])

    def test_receiving_scenarios_conserve_budget_and_nonreceiving_points(self):
        from nfl_workload_scenarios import receiving_scenarios
        records=[dict(player_id="0",projection_fd=16.6,targets=9.53,receptions=6.86,
                      receiving_yards=59,receiving_td=.29),
                 dict(player_id="1",projection_fd=20.6,targets=8.82,receptions=6.23,
                      receiving_yards=50.79,receiving_td=.33)]
        result=receiving_scenarios(pool(),records,team_pass_attempts=36,other_targets=17)
        self.assertEqual(len(result["scenarios"]),9)
        for s in result["scenarios"]:
            self.assertAlmostEqual(sum(p["targets"] for p in s["players"]),s["pair_targets"])
            self.assertLessEqual(s["pair_targets"]+s["other_targets"],s["pass_attempts"]+1e-8)
            for p,old in zip(s["players"],records):
                self.assertAlmostEqual(p["projection_fd"]-old["projection_fd"],
                    (p["targets"]-old["targets"])*p["receiving_fd_per_target"])
                self.assertLessEqual(p["receptions"],p["targets"])
        with self.assertRaises(ValueError):
            receiving_scenarios(pool(),records,team_pass_attempts=35,other_targets=17)
        with self.assertRaises(ValueError):
            receiving_scenarios(pool(),records,team_pass_attempts=36,other_targets=17,
                                cutoff_utc="2026-11-25T23:00:00Z")
