"""Leakage-safe DAILY minutes calibration. Historical rows must be completed games."""
import pandas as pd
import numpy as np

REQUIRED = {'slate_date','fanduel_id','projected_minutes','actual_minutes'}

def audit_actuals(history, as_of_date=None, min_samples=20):
    h=history.copy()
    missing=REQUIRED-set(h.columns)
    if missing: raise ValueError('Missing actuals columns: '+', '.join(sorted(missing)))
    h['slate_date']=pd.to_datetime(h['slate_date'],errors='coerce')
    if as_of_date is not None:
        cutoff=pd.to_datetime(as_of_date)
        h=h[h.slate_date<cutoff].copy() # strictly prior to slate, never same-day lookahead
    for c in ('projected_minutes','actual_minutes'):
        h[c]=pd.to_numeric(h[c],errors='coerce')
    h=h.dropna(subset=['slate_date','fanduel_id','projected_minutes','actual_minutes'])
    h=h[h.projected_minutes.between(0,48)&h.actual_minutes.between(0,70)]
    if 'played_status' in h:
        h=h[~h.played_status.astype(str).str.lower().isin(['dnp','out','inactive'])]
    h=h.drop_duplicates(['slate_date','fanduel_id'],keep='last')
    h['daily_error']=h.actual_minutes-h.projected_minutes
    n=len(h)
    bias=float(h.daily_error.mean()) if n else np.nan
    mae=float(h.daily_error.abs().mean()) if n else np.nan
    return h, {'n':n,'mean_actual_minus_daily':bias,'daily_mae':mae,'calibration_eligible':n>=min_samples}

def evaluate_bias_correction(history, as_of_date=None, min_train=20):
    """Walk-forward validation: train on strictly earlier dates; compare MAE with baseline."""
    h,_=audit_actuals(history,as_of_date,min_samples=min_train)
    out=[]
    for date, test in h.groupby('slate_date',sort=True):
        train=h[h.slate_date<date]
        if len(train)<min_train: continue
        bias=float(train.daily_error.mean())
        for _,r in test.iterrows():
            corrected=float(np.clip(r.projected_minutes+bias,0,48))
            out.append({'slate_date':date.date().isoformat(),'fanduel_id':r.fanduel_id,'daily_minutes':r.projected_minutes,'actual_minutes':r.actual_minutes,'bias_from_prior_games':bias,'calibrated_minutes':corrected,'daily_abs_error':abs(r.projected_minutes-r.actual_minutes),'calibrated_abs_error':abs(corrected-r.actual_minutes)})
    rows=pd.DataFrame(out)
    if rows.empty:return rows,{'validated':False,'reason':'Insufficient prior dated actuals for walk-forward validation'}
    improvement=float(rows.daily_abs_error.mean()-rows.calibrated_abs_error.mean())
    return rows,{'validated':True,'n':len(rows),'daily_mae':float(rows.daily_abs_error.mean()),'calibrated_mae':float(rows.calibrated_abs_error.mean()),'mae_improvement':improvement,'correction_improves_mae':improvement>0}
