from pathlib import Path
from tempfile import TemporaryDirectory
import pandas as pd
from post_slate_audit import audit_players

def run():
    with TemporaryDirectory() as tmp:
        r=Path(tmp)/'research.csv'; a=Path(tmp)/'actual.csv'
        pd.DataFrame({'fanduel_id':['123-1']*1,'fanduel_name':['Player One'],'adjusted_fd_points':[20.0],'adjusted_minutes':[30]}).to_csv(r,index=False)
        pd.DataFrame({'lineup':['L']*9,'player':['Player One']*9,'actual_fd':[12.0]*9}).to_csv(a,index=False)
        try: audit_players(r,a)
        except ValueError: pass
        else: raise AssertionError('Duplicate player in lineup must fail')
        pd.DataFrame({'lineup':['L'],'player':['Player One'],'actual_fd':[12.0]}).to_csv(a,index=False)
        try: audit_players(r,a)
        except ValueError: pass
        else: raise AssertionError('Eight-player lineup must fail')
    root=Path(__file__).resolve().parent
    res=audit_players(root/'data/nov20_research_v33_full.csv',root.parent/'Nov20_Post_Slate_Player_Scores.csv')
    assert len(res)==17 and res.exposures.sum()==45
    assert abs(res.loc[res.player=='Josh Giddey','error_fd'].iloc[0]+20.249702)<.001
    print('post-slate audit tests passed')
if __name__=='__main__':run()
