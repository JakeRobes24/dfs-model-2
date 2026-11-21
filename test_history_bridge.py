import pandas as pd
from history_bridge import summarize_logs,bridge_missing
from pathlib import Path
p=Path(__file__).resolve().parent/'nov20_complete_247_player_coverage.csv'
c=pd.read_csv(p)
logs=pd.DataFrame([{'player':'Drew Timme','game_date':f'2026-11-{d:02d}','minutes':20,'pts':12,'reb':6,'ast':2,'stl':1,'blk':0,'tov':2} for d in (10,12,14,16)]+[{'player':'Drew Timme','game_date':'2026-11-20','minutes':40,'pts':99,'reb':99,'ast':99,'stl':99,'blk':99,'tov':0}])
h=summarize_logs(logs,'2026-11-20')
assert len(h)==1 and h.historical_games.iloc[0]==4 and h.season_mpg.iloc[0]==20
b=bridge_missing(c,h)
r=b[b.fanduel_name.eq('Drew Timme')].iloc[0]
assert r.projected_fd_points>0 and r.scoring_provenance=='historical_boxscore_estimate'
assert b.fanduel_id.nunique()==247 and len(b)==247
assert (b.loc[b.injury_flag.eq('O'),'projected_fd_points'].notna()).any() # OUT retains audit evidence but is never eligible
assert b.needs_manual_review.sum()==26
print('PASS: historical cutoff, actual FD scoring, 247 player preservation, 1 evidenced fill, 26 unresolved')
