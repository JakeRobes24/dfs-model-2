import copy
import unittest
from nfl_prelock_challenger import compare_prelock_candidates

TIME = "2026-11-22T17:00:00Z"
POSITIONS = ["QB","RB","RB","WR","WR","WR","TE","RB","DEF"]
SLOTS = ["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DEF"]


def inputs():
    players = [
        {"player_id": str(i), "salary": 5000, "positions": [pos], "projection_fd": 10+i, "asof_utc": TIME}
        for i, pos in enumerate(POSITIONS)
    ]
    snapshot = {"contest_id": "136799", "slate_date": "2026-11-22", "source_version": "fixture",
                "cutoff_utc": TIME, "salary_cap": 60000, "players": players}
    candidate = {"candidate_id": "A", "contest_id": "136799", "slate_date": "2026-11-22",
                 "created_utc": TIME, "slots": dict(zip(SLOTS, [str(i) for i in range(9)]))}
    return snapshot, candidate


class PrelockChallengerTests(unittest.TestCase):
    def test_valid(self):
        s,c = inputs()
        self.assertEqual(compare_prelock_candidates(s,[c])[0]["projected_fd"], 126)

    def test_no_hindsight(self):
        s,c = inputs()
        before = compare_prelock_candidates(s,[c])
        s["players"][0]["actual_fd"] = 10000
        self.assertEqual(before, compare_prelock_candidates(s,[c]))

    def test_missing_projection_rejected(self):
        s,c = inputs()
        s["players"][0]["projection_fd"] = None
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_late_projection_rejected(self):
        s,c = inputs()
        s["players"][0]["asof_utc"] = "2026-11-22T18:00:00Z"
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_late_candidate_rejected(self):
        s,c = inputs()
        c["created_utc"] = "2026-11-22T18:00:00Z"
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_wrong_contest_rejected(self):
        s,c = inputs()
        c["contest_id"] = "other"
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_duplicate_player_rejected(self):
        s,c = inputs()
        c["slots"]["RB2"] = "1"
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_position_rejected(self):
        s,c = inputs()
        c["slots"]["TE"] = "8"
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_salary_cap_rejected(self):
        s,c = inputs()
        s["players"][0]["salary"] = 25000
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])

    def test_missing_timezone_rejected(self):
        s,c = inputs()
        s["cutoff_utc"] = "2026-11-22T17:00:00"
        with self.assertRaises(ValueError): compare_prelock_candidates(s,[c])


if __name__ == "__main__":
    unittest.main()
