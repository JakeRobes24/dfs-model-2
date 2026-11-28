"""Restore the two named private evidence ZIPs and run with --archive-dir."""
from pathlib import Path
import argparse
import zipfile
import hashlib
import json
import pandas as pd
from temporal_component_transfer import paired_archive, transfer_grid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--archive-dir',type=Path,required=True)
args = parser.parse_args()
p = args.archive_dir
archives = {
    'DFS_Model_2_Tracked_Opportunity_Validation.zip':'ff64f55a7b2fbf4bb86c31babb76947265e2f0f0b849542bf0c917ca2cd09fc2',
    'DFS_Model_2_Shooting_and_Route_Workload_Validation.zip':'83d73f04d82ecb914583c40e454fef90f64d3e4ecb7a9a1ea5bdb36a2764c0a4',
}
for name,digest in archives.items():
    if hashlib.sha256((p/name).read_bytes()).hexdigest() != digest:
        raise ValueError('Archive hash differs: '+name)
z,r = [zipfile.ZipFile(p/name) for name in archives]
pol=['Four-game outcome average','Pooled conversion','Recent opportunity rate','Recent opportunities and pooled conversion']
out={}
for stat in ('rebounds','field_goals','assists'):
    f=pd.read_csv(z.open(f'nba-tracking-{stat}.csv'))
    w=paired_archive(f,['date','game_id','nba_id','team'],pol,actual='outcome',forecast='prediction')
    train=w[w.date<'2026-11-15'];test=w[w.date>='2026-11-15']
    out['NBA '+stat]={'train_n':len(train),'test_n':len(test),'train_dates':train.date.nunique(),'test_dates':test.date.nunique(),'results':{c:transfer_grid(train,test,pol[0],c,period='date',chronology='date') for c in pol[1:]}}
pol=['Actual scoring average','Expected scoring average','Equal actual and expected blend']
sets=[]
for season in (2025,2026):
    f=pd.read_csv(z.open(f'nfl-expected-{season}.csv'))
    w=paired_archive(f,['date','week','game_id','team','gsis_id','position','channel'],pol,actual='actual',forecast='forecast')
    if ((w[pol[0]]+w[pol[1]])/2-w[pol[2]]).abs().max()>=1e-8:
        raise ValueError('Archived blend mismatch')
    sets.append(w)
for channel in ('receiving','rushing'):
    for position in ('all','RB','WR','TE'):
        train,test=[x[(x.channel==channel)&((x.position==position)|(position=='all'))] for x in sets]
        out[f'NFL {channel} {position}']={'train_n':len(train),'test_n':len(test),'results':transfer_grid(train,test,pol[0],pol[1],period='week',chronology='date',minimum_rows=100)}
f=pd.read_csv(r.open('route-holdout.csv'))
pol=['Four-game expected','Recent route share and expected','Equal route blend and expected']
j=pd.read_csv(r.open('route-history-matched.csv'))[['game_id','gameday']].drop_duplicates()
if j.game_id.duplicated().any():
    raise ValueError('Ambiguous game dates')
f=f.merge(j,on='game_id',validate='many_to_one').rename(columns={'gameday':'date'})
for metric,actual,forecast in [('targets','actual_targets','targets'),('receiving FD','actual_fd','fd')]:
    w=paired_archive(f,['date','week','game_id','team','gsis_id','position'],pol,actual=actual,forecast=forecast)
    for position in ('all','RB','WR','TE'):
        q=w[(w.position==position)|(position=='all')];train=q[q.week<9];test=q[q.week>=9]
        out[f'NFL routes {metric} {position}']={'train_n':len(train),'test_n':len(test),'results':transfer_grid(train,test,pol[0],pol[1],period='week',chronology='date',minimum_rows=100)}
print(json.dumps(out,indent=2))
