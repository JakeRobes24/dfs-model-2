"""Research-only replay of existing nine-player rosters with history residuals.

Earlier box-score-only forecast errors are transferred to frozen reviewed
means as an explicit experiment. Not calibrated contest-level probabilities.
Never optimize from the target outcomes or invent a historical roster.
"""
from collections import Counter
from datetime import date
import numpy as np
import pandas as pd
from model import SLOTS, allowed_slots
from nba_history_ranges import historical_forecasts,_residuals,_band,_interval_score
from nba_simulation import OutcomeDraws

POLICIES=('point_residual','paired_minutes_rate')

def simulate_archived_rosters(records,pool,rosters,*,slate,draws=4000,seed=42):
    if type(slate) is not date or not isinstance(draws,int) or not 100<=draws<=20000:
        raise ValueError('Require exact slate date and 100–20,000 draws')
    required={'fanduel_id','eligible','salary','team','roster_eligibility','adjusted_minutes','adjusted_fd_points'}
    if not required<=set(pool) or not {'lineup','slot','fanduel_id'}<=set(rosters):
        raise ValueError('Require original contest pool and saved rosters')
    if pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique or rosters.empty:
        raise ValueError('Require unique contest pool and nonempty rosters')
    if rosters.lineup.isna().any() or rosters.fanduel_id.isna().any():
        raise ValueError('Missing roster identity')
    selected=pool.loc[pool.fanduel_id.isin(rosters.fanduel_id)].copy().sort_values('fanduel_id')
    if set(selected.fanduel_id)!=set(rosters.fanduel_id) or not selected.eligible.astype(str).str.lower().eq('true').all():
        raise ValueError('Roster contains unknown or ineligible player')
    fields=['salary','adjusted_minutes','adjusted_fd_points']
    selected[fields]=selected[fields].apply(pd.to_numeric,errors='coerce')
    if (not np.isfinite(selected[fields]).all().all() or not selected.salary.gt(0).all()
            or not selected.adjusted_minutes.between(10,48).all()
            or not selected.adjusted_fd_points.gt(0).all()
            or not (selected.adjusted_fd_points/selected.adjusted_minutes).le(5).all()
            or not selected.team.astype(str).str.fullmatch('[A-Z]{2,3}').all()):
        raise ValueError('Unsupported archived roster inputs')
    lookup=selected.set_index('fanduel_id')
    for _,g in rosters.groupby('lineup',sort=False):
        if len(g)!=9 or not g.fanduel_id.is_unique or Counter(g.slot)!=Counter(SLOTS):
            raise ValueError('Require exactly nine legal roster slots')
        players=lookup.loc[g.fanduel_id]
        if (players.salary.sum()>60000 or players.team.value_counts().max()>4
                or any(slot not in allowed_slots(lookup.loc[pid,'roster_eligibility'])
                       for pid,slot in zip(g.fanduel_id,g.slot))):
            raise ValueError('Archived roster violates contest rules')
    prior=historical_forecasts(records,cutoff_day=slate)
    dates={r['date'] for r in prior}
    if len(prior)<100 or len(dates)<5:
        raise ValueError('Insufficient earlier historical residuals')
    rng=np.random.default_rng(seed)
    m=selected.adjusted_minutes.to_numpy()
    fp=selected.adjusted_fd_points.to_numpy()
    outputs={p:np.empty((draws,len(selected))) for p in POLICIES}
    minutes=np.empty((draws,len(selected)))
    for i,(base_m,base_fp) in enumerate(zip(m,fp)):
        band=[r for r in prior if _band(r['minutes'])==_band(base_m)]
        cohort=band if len(band)>=30 and len({r['date'] for r in band})>=3 else prior
        errors=_residuals(cohort)
        errors=errors-errors.mean(axis=0)
        sample=errors[rng.integers(len(errors),size=draws)]
        minutes[:,i]=np.clip(base_m+sample[:,0],1/60,60)
        outputs['point_residual'][:,i]=base_fp+sample[:,1]
        outputs['paired_minutes_rate'][:,i]=minutes[:,i]*(base_fp/base_m+sample[:,3])
    models={p:OutcomeDraws(pd.Index(selected.fanduel_id),minutes.copy(),x) for p,x in outputs.items()}
    return models,dict(training_rows=len(prior),training_dates=len(dates),
                       training_latest=max(dates),players=len(selected),draws=draws,
                       certified=False)

def evaluate_archived_rosters(models,pool,rosters,actuals):
    """Only complete verified played rosters enter the matched comparison.

    DNP/short appearances are outside the conditional training scope.
    Missing results are not imputed or used for any forecast construction.
    """
    required={'fanduel_id','actual_minutes','actual_points','verified_outcome','nba_source'}
    if not required<=set(actuals) or not actuals.fanduel_id.is_unique:
        raise ValueError('Require unique verified outcomes')
    a=actuals.copy()
    a[['actual_minutes','actual_points']]=a[['actual_minutes','actual_points']].apply(pd.to_numeric,errors='coerce')
    valid=a.loc[a.verified_outcome.eq('played') & a.nba_source.fillna('').astype(str).str.strip().ne('')
                & a.actual_minutes.between(10,60) & np.isfinite(a.actual_points)]
    by_id=valid.set_index('fanduel_id').actual_points
    reviewed=pool.set_index('fanduel_id').adjusted_fd_points.astype(float)
    totals={}
    excluded=[]
    for label,g in rosters.groupby('lineup',sort=False):
        ids=g.fanduel_id
        if not set(ids)<=set(by_id.index):
            excluded.append(str(label))
            continue
        totals[label]=dict(actual=float(by_id.loc[ids].sum()),reviewed=float(reviewed.loc[ids].sum()))
    rows=[]
    pairs=[]
    kept=rosters.loc[rosters.lineup.isin(totals)]
    if not kept.empty:
        for policy,model in models.items():
            for r in model.lineup_ranges(kept).to_dict('records'):
                y=totals[r['lineup']]['actual']
                rows.append(dict(policy=policy,**r,**totals[r['lineup']],
                    covered=bool(r['fd_p10']<=y<=r['fd_p90']),
                    interval_score=_interval_score(y,r['fd_p10'],r['fd_p90'])))
            for r in model.compare_lineups(kept).to_dict('records'):
                a,b=r['lineup'],r['alternative']
                gap=totals[a]['actual']-totals[b]['actual']
                p=r['lineup_ahead_share']+.5*r['tie_share']
                pairs.append(dict(policy=policy,**r,actual_gap=gap,
                    reviewed_gap=totals[a]['reviewed']-totals[b]['reviewed'],
                    brier=(p-float(gap>0))**2 if abs(gap)>1e-9 else None))
    return dict(lineups=rows,pairs=pairs,excluded_lineups=excluded,
                status='One-date retrospective, shared player draws; conditional played-only; no payout or contest win probability',
                certified=False)
