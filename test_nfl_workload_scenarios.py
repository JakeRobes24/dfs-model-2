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
