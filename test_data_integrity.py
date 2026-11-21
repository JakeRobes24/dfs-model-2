import tempfile
import unittest
from pathlib import Path
import pandas as pd
from data_integrity import load_research

class IntegrityTests(unittest.TestCase):
    def test_saved_247_player_pool(self):
        p=Path(__file__).parent/'data/nov20_research_v33_full.csv'
        d,meta=load_research(p,expected_rows=247)
        self.assertEqual(d.fanduel_id.nunique(),247)
        self.assertEqual(meta['columns'],324)
    def test_duplicate_id_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.csv'
            pd.DataFrame([{'fanduel_id':'1','fanduel_name':'A','salary':5000,'position':'PG','roster_eligibility':'PG','adjusted_fd_points':25}]*2).to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'duplicate'):load_research(p)
    def test_missing_file_fails_closed(self):
        with self.assertRaises(FileNotFoundError):load_research('/no-such-dfs-pool.csv')
if __name__=='__main__':unittest.main()
