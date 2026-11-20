"""Audit full contest coverage; never silently treat an unmatched player as a bad player."""
import pandas as pd
from model import norm

# Verified against original contest/projection reconciliation, not fuzzy guesses.
VERIFIED_ALIASES = {
 'alexsarr':'alexandresarr', 'mobamba':'mohamedbamba',
 'nicclaxton':'nicolasclaxton','svimykhailiuk':'sviatoslavmykhailiuk',
 'ronaldholland':'ronhollandii','moritzwagner':'moewagner',
 'bubcarrington':'carltoncarrington'
}

def audit_pool(contest, reconciled, historical=None, supplemental=None):
    """Full contest rows plus projections, preserving OUT and missing-source flags.
    supplemental: fanduel_id, projected_minutes, projected_fd_points, provenance
    historical: fanduel_id, season_mpg,last5_mpg,last10_mpg, optionally actual_fppm
    """
    c=contest.copy();r=reconciled.copy()
    if 'name' in c.columns:c=c.rename(columns={'name':'fanduel_name'})
    for col in ['fanduel_id','fanduel_name','salary','injury_flag']:
        if col not in c:raise ValueError(f'Contest missing {col}')
    keep=['fanduel_id','projection_name','projected_minutes','projected_fd_points','match_type']
    d=c.merge(r[keep],on='fanduel_id',how='left',validate='one_to_one')
    if supplemental is not None and len(supplemental):
        sup=supplemental.copy()
        if sup.fanduel_id.duplicated().any():raise ValueError('Duplicate supplemental IDs')
        d=d.merge(sup,on='fanduel_id',how='left',suffixes=('','_supp'),validate='one_to_one')
        for col in ['projected_minutes','projected_fd_points']:
            d[col]=d[col].fillna(d[col+'_supp'])
    if historical is not None and len(historical):
        h=historical.copy()
        if h.fanduel_id.duplicated().any():raise ValueError('Duplicate historical IDs')
        d=d.merge(h,on='fanduel_id',how='left',validate='one_to_one')
    d['coverage_status']='matched_DAILY'
    missing=d.projected_fd_points.isna()
    d.loc[missing,'coverage_status']='missing_scoring_projection'
    d.loc[d.injury_flag.fillna('').str.upper().eq('O'),'coverage_status']='excluded_contest_OUT'
    d['needs_manual_review']=missing & ~d.injury_flag.fillna('').str.upper().eq('O')
    assert len(d)==len(c) and d.fanduel_id.nunique()==len(c)
    return d
