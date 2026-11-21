import pandas as pd
from model import consensus,optimize
from evidence import validate_sources,evaluate_minutes,scenario_projections
b=pd.read_csv('nov20_reconciled_example.csv')
d=consensus(b)
assert len(d)==len(b)
assert (d.loc[d.injury_flag.eq('O'),'eligible']==False).all()
assert (d.loc[d.minutes_method.eq('DAILY_only_unverified'),'confidence']=='low').all()
l=optimize(d,number=4)
assert l.lineup.nunique()==4
for _,g in l.groupby('lineup'):
    assert len(g)==9 and g.fanduel_id.nunique()==9 and g.salary.sum()<=60000
src=pd.DataFrame([{'player':'A','source':'X','minutes':32},{'player':'A','source':'Y','minutes':33}]);assert len(validate_sources(src))==2
act=pd.DataFrame([{'player':'A','actual_minutes':31}]);_,s=evaluate_minutes(src,act);assert s.samples.sum()==2
changed=scenario_projections(d,pd.DataFrame([{'player':b.iloc[0].fanduel_name,'minutes_delta':2}]))
assert changed.iloc[0].adjusted_minutes==d.iloc[0].adjusted_minutes+2
print('PASS: reconciliation, injury exclusion, 4 legal lineups, evidence audit, accuracy, scenario')

from model import norm
from pool_coverage import audit_pool,VERIFIED_ALIASES
from historical import historical_minutes
matched = b
all_contest = pd.read_csv('data/nov20_research_v33_full.csv', low_memory=False)[
    ['fanduel_id', 'fanduel_name', 'salary', 'injury_flag']
]
coverage=audit_pool(all_contest,matched)
assert len(coverage)==247
assert coverage.coverage_status.eq('matched_DAILY').sum()>0
assert coverage.needs_manual_review.sum()>0
assert matched.match_type.eq('verified_alias').sum()==7
assert all(norm(k) in VERIFIED_ALIASES for k in ['Alex Sarr','Mo Bamba','Nic Claxton','Svi Mykhailiuk','Ronald Holland','Moritz Wagner','Bub Carrington'])
logs=pd.DataFrame([{'player':'A','game_date':'2026-11-18','minutes':32},{'player':'A','game_date':'2026-11-20','minutes':40}])
h=historical_minutes(logs,'2026-11-20');assert len(h)==1 and h.iloc[0].season_mpg==32
print('PASS: 247-player coverage, verified aliases, historical cutoff')
