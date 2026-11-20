import tempfile
from pathlib import Path
import pandas as pd
from source_ingest import read_logs,apply_verified_logs

def run():
    with tempfile.TemporaryDirectory() as t:
        path=Path(t)/'logs.csv'
        d=pd.DataFrame([{'Date':f'2026-11-{10+i:02d}','Player':'Drew Timme','Minutes':20+i,'Points':10+i,'Rebounds':5,'Assists':2,'Steals':1,'Blocks':0,'Turnovers':1} for i in range(4)])
        d.to_csv(path,index=False)
        parsed=read_logs(path)
        assert len(parsed)==4
        coverage=pd.DataFrame([{'fanduel_id':'test1','fanduel_name':'Drew Timme','projected_minutes':float('nan'),'projected_fd_points':float('nan'),'injury_flag':''},{'fanduel_id':'test2','fanduel_name':'Other Player','projected_minutes':float('nan'),'projected_fd_points':float('nan'),'injury_flag':''}])
        result,history=apply_verified_logs(coverage,path)
        assert result.loc[0,'projected_fd_points']>0
        assert result.loc[1,'scoring_provenance']=='unresolved'
        # No leakage from slate date
        d.loc[len(d)]={'Date':'2026-11-20','Player':'Drew Timme','Minutes':40,'Points':90,'Rebounds':5,'Assists':2,'Steals':1,'Blocks':0,'Turnovers':1}
        d.to_csv(path,index=False)
        result2,history2=apply_verified_logs(coverage,path)
        assert abs(result2.loc[0,'projected_fd_points']-result.loc[0,'projected_fd_points'])<1e-8
        print('Source adapter, missing projection bridge, and cutoff tests PASS (synthetic fixtures only)')
if __name__=='__main__':run()
