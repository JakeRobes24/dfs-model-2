"""Explicit, auditable research scoring scenarios; no claim of calibrated ceiling or ownership."""
import numpy as np
import pandas as pd
from research_integration import prepare_research_pool
from model import optimize

def scenario_pool(research, *, mode='baseline', exclude_questionable=True, exclude_huerter=True, uncertainty_weight=0.35, ceiling_weight=0.20):
    """Rank lineups using transparent sensitivity scores, not a claimed probabilistic ceiling."""
    if mode not in ('baseline','risk_adjusted','upside_proxy'):
        raise ValueError('Unknown scenario')
    d=prepare_research_pool(research,exclude_questionable=exclude_questionable,exclude_huerter=exclude_huerter)
    d['baseline_scenario_fd']=pd.to_numeric(d.adjusted_fd_points,errors='coerce')
    l5=pd.to_numeric(d.historical_l5_fd,errors='coerce')
    l10=pd.to_numeric(d.historical_l10_fd,errors='coerce')
    recent=(l5+l10)/2
    recent=recent.where(l5.notna()&l10.notna(),l5.fillna(l10))
    high=pd.to_numeric(d.get('v27_bulk_l10_fd_high',pd.Series(np.nan,index=d.index)),errors='coerce')
    # A historical best is not a forecast ceiling. Cap its effect to avoid overweighting an outlier.
    d['historical_upside_proxy']=((high-recent).clip(lower=0,upper=25)).fillna(0)
    minutes=pd.to_numeric(d.adjusted_minutes,errors='coerce')
    histminutes=pd.to_numeric(d.historical_l5_minutes,errors='coerce')
    d['minutes_gap_abs']=(minutes-histminutes).abs()
    d['uncertainty_penalty']=np.where(d.confidence.astype(str).str.lower().isin(['low','missing','unverified']),2.0,0.0)
    d['uncertainty_penalty']+=np.minimum(d.minutes_gap_abs.fillna(6),12)/4
    d['uncertainty_penalty']+=np.where(d.historical_l5_fd.isna(),1.5,0)
    if mode=='risk_adjusted':
        d['adjusted_fd_points']=d.baseline_scenario_fd-uncertainty_weight*d.uncertainty_penalty
    elif mode=='upside_proxy':
        d['adjusted_fd_points']=d.baseline_scenario_fd+ceiling_weight*d.historical_upside_proxy-uncertainty_weight*d.uncertainty_penalty
    d['scenario_mode']=mode
    d['scenario_caveat']='Historical highs and uncertainty penalties are transparent sensitivity proxies, not calibrated probabilities or verified projections.'
    return d

def compare_scenarios(research, *, max_overlap=7, number=4, exclude_questionable=True, exclude_huerter=True):
    all_lineups=[];all_pool=[]
    for mode in ('baseline','risk_adjusted','upside_proxy'):
        p=scenario_pool(research,mode=mode,exclude_questionable=exclude_questionable,exclude_huerter=exclude_huerter)
        l=optimize(p,number=number,max_overlap=max_overlap)
        if l.empty:raise ValueError(f'No legal lineups under {mode}')
        l['scenario']=mode
        all_lineups.append(l)
        all_pool.append(p)
    return pd.concat(all_pool,ignore_index=True),pd.concat(all_lineups,ignore_index=True)

def verify_lineups(lineups, source_pool):
    errors=[]
    slots=['PG','SG','SF','PF','C','G/F','F/C','UTIL','UTIL']
    for (scenario,k),g in lineups.groupby(['scenario','lineup']):
        if len(g)!=9 or g.fanduel_id.nunique()!=9:errors.append(f'{scenario} {k}: roster/duplicates')
        if sorted(g.slot.tolist())!=sorted(slots):errors.append(f'{scenario} {k}: slots')
        if g.salary.sum()>60000:errors.append(f'{scenario} {k}: salary')
        for _,r in g.iterrows():
            z=source_pool[source_pool.fanduel_id.eq(r.fanduel_id)]
            if len(z)!=1 or not bool(z.iloc[0].eligible):errors.append(f'{scenario} {k}: ineligible {r.player}')
    if errors:raise AssertionError('; '.join(errors))
    return True
