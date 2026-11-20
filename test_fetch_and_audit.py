import tempfile
from pathlib import Path
import pandas as pd
from fetch_and_audit import audit

def test_audit():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        pd.DataFrame([
          {'fanduel_id':'1','fanduel_name':'Example Player','salary':3500,'injury_flag':'','projected_minutes':None,'projected_fd_points':None},
          {'fanduel_id':'2','fanduel_name':'Out Player','salary':3500,'injury_flag':'O','projected_minutes':None,'projected_fd_points':None},
        ]).to_csv(root/'pool.csv',index=False)
        pd.DataFrame([{'player':'Example Player','game_date':f'2026-11-{i:02d}','minutes':30,'pts':20,'reb':5,'ast':5,'stl':1,'blk':1,'tov':2} for i in (10,12,14)] +
                     [{'player':'Example Player','game_date':'2026-11-20','minutes':45,'pts':80,'reb':20,'ast':20,'stl':5,'blk':5,'tov':0}]).to_csv(root/'logs.csv',index=False)
        r=audit(root/'pool.csv',root/'logs.csv',root/'out')
        assert r['historical_scoring_fills']==1,r
        assert r['active_without_scoring']==0,r
        assert r['out_excluded']==1,r
        assert r['historical_log_rows_before_slate']==3,r
if __name__=='__main__':test_audit();print('PASS: source import, historical fill, out exclusion, no future leakage')
