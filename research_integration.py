"""Research-to-optimizer bridge. Scenario values are never labeled verified forecasts."""
import numpy as np
import pandas as pd
from model import optimize

REQUIRED={'fanduel_id','fanduel_name','salary','roster_eligibility','projected_minutes','projected_fd_points'}

def prepare_research_pool(research, *, projection_column='v33_tentative_fd_for_comparison', exclude_questionable=True, exclude_huerter=False):
    missing=REQUIRED-set(research.columns)
    if missing:raise ValueError(f'Research input missing required fields: {sorted(missing)}')
    if research.fanduel_id.isna().any() or research.fanduel_id.duplicated().any():raise ValueError('Missing or duplicate FanDuel IDs')
    d=research.copy()
    d['salary']=pd.to_numeric(d.salary,errors='coerce')
    if d.salary.isna().any():raise ValueError('Missing salary')
    d['projected_fd_points']=pd.to_numeric(d.projected_fd_points,errors='coerce')
    if projection_column not in d.columns:raise ValueError(f'Missing scenario field {projection_column}')
    d['adjusted_fd_points']=pd.to_numeric(d[projection_column],errors='coerce')
    d['adjusted_minutes']=pd.to_numeric(d.get('v32_conservative_minutes_scenario',d.projected_minutes),errors='coerce').fillna(pd.to_numeric(d.projected_minutes,errors='coerce'))
    d['confidence']=d.get('v30_confidence',pd.Series('unverified',index=d.index)).fillna('unverified').astype(str)
    d['minutes_method']=d.get('v33_status_action',pd.Series('research_scenario',index=d.index)).fillna('research_scenario').astype(str)
    d['injury_flag']=d.get('injury_flag',pd.Series('',index=d.index)).fillna('').astype(str)
    d['official_status_snapshot']=d.get('v29_official_0915_status',pd.Series('',index=d.index)).fillna('').astype(str).str.upper()
    d['eligible']=~(d.injury_flag.str.upper().eq('O') | d.official_status_snapshot.eq('OUT'))
    if exclude_questionable:d.loc[d.official_status_snapshot.eq('QUESTIONABLE'),'eligible']=False
    if exclude_huerter:d.loc[d.fanduel_name.str.casefold().eq('kevin huerter'),'eligible']=False
    d['projection_warning']=np.where(d['adjusted_fd_points'].isna(),'No research scenario projection',np.where(d.official_status_snapshot.eq('QUESTIONABLE'),'Questionable in morning snapshot','Research scenario: not verified for lock'))
    d['research_projection_source']=projection_column
    d['historical_l5_fd']=pd.to_numeric(d.get('v27_bulk_l5_fd_avg',pd.Series(np.nan,index=d.index)),errors='coerce')
    d['historical_l10_fd']=pd.to_numeric(d.get('v27_bulk_l10_fd_avg',pd.Series(np.nan,index=d.index)),errors='coerce')
    d['historical_l5_minutes']=pd.to_numeric(d.get('v27_bulk_l5_minutes',pd.Series(np.nan,index=d.index)),errors='coerce')
    d['minutes_disagreement']=d['historical_l5_minutes']-pd.to_numeric(d.projected_minutes,errors='coerce')
    return d

def optimize_research(research,number=4,max_overlap=7,**kwargs):
    pool=prepare_research_pool(research,**kwargs)
    return pool,optimize(pool,number=number,max_overlap=max_overlap)

def lineup_summary(lineups):
    if lineups.empty:return pd.DataFrame(columns=['lineup','salary','scenario_fd','players'])
    return lineups.groupby('lineup').agg(salary=('salary','sum'),scenario_fd=('adjusted_fd_points','sum'),players=('player','nunique')).reset_index()
