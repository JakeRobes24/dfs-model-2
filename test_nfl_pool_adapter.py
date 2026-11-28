import copy
import unittest
from nfl_pool_adapter import build_nfl_snapshot

TIME="2026-11-22T17:00:00Z"


def fixture():
    positions=["QB","RB","RB","WR","WR","WR","TE","RB","DEF"]
    rows=[{"player_id":str(i),"salary":5000,"positions":[pos],"projection_fd":10+i,
           "asof_utc":TIME,"contest_id":"136799","slate_date":"2026-11-22",
           "team":"TEAM","game":"TEAM@OPP","status":"available"} for i,pos in enumerate(positions)]
    kw={"contest_id":"136799","slate_date":"2026-11-22","source_version":"reconciled-v1",
        "cutoff_utc":TIME,"expected_player_ids":[str(i) for i in range(9)]}
    return rows,kw


class NFLAdapterTests(unittest.TestCase):
    def test_complete_pool(self):
        rows,kw=fixture()
        self.assertEqual(len(build_nfl_snapshot(rows,**kw)["players"]),9)

    def test_partial_pool_rejected(self):
        rows,kw=fixture()
        with self.assertRaises(ValueError):build_nfl_snapshot(rows[:-1],**kw)

    def test_unknown_id_rejected(self):
        rows,kw=fixture()
        rows[0]["player_id"]="unknown"
        with self.assertRaises(ValueError):build_nfl_snapshot(rows,**kw)

    def test_missing_projection_rejected(self):
        rows,kw=fixture()
        rows[0]["projection_fd"]=None
        with self.assertRaises(ValueError):build_nfl_snapshot(rows,**kw)

    def test_future_source_rejected(self):
        rows,kw=fixture()
        rows[0]["asof_utc"]="2026-11-22T18:00:00Z"
        with self.assertRaises(ValueError):build_nfl_snapshot(rows,**kw)

    def test_out_status_rejected(self):
        rows,kw=fixture()
        rows[0]["status"]="out"
        with self.assertRaises(ValueError):build_nfl_snapshot(rows,**kw)

    def test_mixed_contest_rejected(self):
        rows,kw=fixture()
        rows[0]["contest_id"]="different"
        with self.assertRaises(ValueError):build_nfl_snapshot(rows,**kw)

    def test_expected_ids_required(self):
        rows,kw=fixture()
        del kw["expected_player_ids"]
        with self.assertRaises(ValueError):build_nfl_snapshot(rows,**kw)


if __name__=="__main__":
    unittest.main()
