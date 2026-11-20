"""Evidence validation and post-slate evaluation; never fetches or invents observations."""
import pandas as pd
import numpy as np
from model import norm

def validate_sources(df):
    required={'player','source','minutes'}
    missing=required-set(df.columns)
    if missing: raise ValueError(f'Missing source columns: {sorted(missing)}')
    e=df.copy()
    e['minutes']=pd.to_numeric(e.minutes,errors='coerce')
    e['valid_minutes']=e.minutes.between(0,48)
    e['independent_group']=e.get('independent_group',e.source).fillna(e.source)
    e['key']=e.player.map(norm)
    e['duplicate_group']=e.duplicated(['key','independent_group'],keep=False)
    if 'observed_at' in e:
        e['observed_at']=pd.to_datetime(e.observed_at,utc=True,errors='coerce')
        e['stale_or_undated']=e.observed_at.isna()
    else:e['stale_or_undated']=True
    return e

def evaluate_minutes(predictions,actuals):
    """predictions: player,source,minutes; actuals: player,actual_minutes.
    Report observed error without treating unobserved outcomes as zero.
    """
    p=predictions.copy();a=actuals.copy()
    if not {'player','source','minutes'}.issubset(p):raise ValueError('Predictions require player,source,minutes')
    if not {'player','actual_minutes'}.issubset(a):raise ValueError('Actuals require player,actual_minutes')
    p['key']=p.player.map(norm);a['key']=a.player.map(norm)
    p['minutes']=pd.to_numeric(p.minutes,errors='coerce');a['actual_minutes']=pd.to_numeric(a.actual_minutes,errors='coerce')
    x=p.merge(a[['key','actual_minutes']],on='key',how='inner')
    x=x[x.minutes.between(0,48)&x.actual_minutes.between(0,60)].copy()
    x['absolute_error']=(x.minutes-x.actual_minutes).abs();x['squared_error']=(x.minutes-x.actual_minutes)**2
    summary=x.groupby('source',as_index=False).agg(samples=('absolute_error','size'),mae=('absolute_error','mean'),mse=('squared_error','mean'))
    summary['rmse']=np.sqrt(summary.mse)
    summary=summary.drop(columns='mse').sort_values(['mae','samples'],ascending=[True,False])
    return x,summary

def scenario_projections(pool, changes):
    """changes: player,minutes_delta[,status]. Explicit scenario only; no claims of probability."""
    d=pool.copy();c=changes.copy()
    if not {'player','minutes_delta'}.issubset(c):raise ValueError('Scenario requires player,minutes_delta')
    c['key']=c.player.map(norm);d['key']=d.fanduel_name.map(norm)
    if c.key.duplicated().any():raise ValueError('Duplicate player in scenario')
    c['minutes_delta']=pd.to_numeric(c.minutes_delta,errors='coerce')
    if c.minutes_delta.isna().any():raise ValueError('Invalid minutes delta')
    d=d.merge(c[['key','minutes_delta']],on='key',how='left');d['minutes_delta']=d.minutes_delta.fillna(0)
    d['adjusted_minutes']=(d.adjusted_minutes+d.minutes_delta).clip(0,48)
    d['adjusted_fd_points']=d.fppm*d.adjusted_minutes
    d['scenario_changed']=d.minutes_delta.ne(0)
    return d.drop(columns=['key'])
