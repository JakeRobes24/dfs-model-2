import csv,io,unittest
from nba_frozen_pool_actuals import audit_frozen_pool
def dump(rows):
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    return out.getvalue()
class ActualsTests(unittest.TestCase):
    def setUp(self):
        self.pool=[{"id":"1","daily_fd":"20","consensus_scenario_fd":"22"},
                   {"id":"2","daily_fd":"10","consensus_scenario_fd":"9"}]
        self.actuals=[{"player_id":"1","actual_fd":"25","result_status":"PLAYED",
                       "source_url":"https://example.org/a","verified_at_utc":"2026-11-23T01:00:00Z"},
                      {"player_id":"2","actual_fd":"","result_status":"DNP","source_url":"","verified_at_utc":""}]
    def audit(self): return audit_frozen_pool(dump(self.pool),dump(self.actuals))
    def test_metrics(self):
        r=self.audit();self.assertEqual(r["paired"]["daily_mae"],5)
        self.assertEqual(r["paired"]["scenario_mae"],3)
        self.assertEqual(r["coverage"]["dnp"],1)
    def test_unreported(self):
        self.actuals.pop();self.assertFalse(self.audit()["complete_full_pool_actuals"])
    def test_missing(self):
        self.actuals[1]["result_status"]="MISSING"
        self.assertFalse(self.audit()["complete_full_pool_actuals"])
    def test_duplicate(self):
        self.actuals.append(self.actuals[0].copy())
        with self.assertRaises(ValueError):self.audit()
    def test_unknown_id(self):
        self.actuals[0]["player_id"]="3"
        with self.assertRaises(ValueError):self.audit()
    def test_no_source(self):
        self.actuals[0]["source_url"]=""
        with self.assertRaises(ValueError):self.audit()
    def test_dnp_zero(self):
        self.actuals[1]["actual_fd"]="0"
        with self.assertRaises(ValueError):self.audit()
    def test_nan(self):
        self.actuals[0]["actual_fd"]="nan"
        with self.assertRaises(ValueError):self.audit()
    def test_no_timestamp(self):
        self.actuals[0]["verified_at_utc"]=""
        with self.assertRaises(ValueError):self.audit()
if __name__=="__main__":unittest.main()
