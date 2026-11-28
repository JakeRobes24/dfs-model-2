"""Compare exact like-for-like NBA reference counts and rates.

A subtotal never fills missing scoring components. Reviewed minutes are
not treated as independently projected box counts.
"""
from nba_distribution_review import bounded
import pandas as pd

WEIGHTS={'points':1.,'rebounds':1.2,'assists':1.5,'steals':3.,'blocks':3.,'turnovers':-1.}
ACTUAL={k:'nba_'+('reboundsTotal' if k=='rebounds' else k) for k in WEIGHTS}
SUBTOTALS={
    'PRA FD-weighted subtotal':('points','rebounds','assists'),
    'FD-weighted subtotal without blocks':('points','rebounds','assists','steals','turnovers'),
    'FD-weighted subtotal without turnovers':('points','rebounds','assists','steals','blocks'),
    'Full six-component FD':tuple(WEIGHTS),
}
DETAIL_FIELDS=('slate_date','fanduel_id','provider','timing_basis','metric',
               'published_at','observed_at','forecast','actual','daily',
               'source_error','daily_error')


def matched_components(row,entry):
    """Return only common finite count support, no inferred reviewed counts."""
    source=entry.get('components')
    if not isinstance(source,dict):
        return []
    observed={}
    baseline={}
    forecast={}
    for k in WEIGHTS:
        f=bounded(source.get(k),0,150)
        a=bounded(getattr(row,ACTUAL[k],None),0,150)
        d=bounded(getattr(row,'daily_box_'+k,None),0,150)
        if a is not None and a.is_integer():
            observed[k]=a
        if f is not None and d is not None:
            forecast[k]=f
            baseline[k]=d
    if set(observed)==set(WEIGHTS):
        total=bounded(row.actual_points,-150,500)
        if total is None or abs(sum(observed[k]*w for k,w in WEIGHTS.items())-total)>.05:
            return []
    keys=set(observed)&set(forecast)&set(baseline)
    sm=bounded(entry.get('minutes'),10,48)
    dm=bounded(row.daily_minutes,10,48)
    am=bounded(row.actual_minutes,10,60)
    rm=bounded(row.adjusted_minutes,10,48)
    rows=[]
    def add(label,f,a,d):
        rows.append((label,f,a,d))
        if None not in (sm,dm,am):
            add_rate=(f/sm,a/am,d/dm)
            rows.append((label+' per minute',*add_rate))
            if rm is not None:
                rows.append((label+' at shared reviewed minutes',rm*f/sm,a,rm*d/dm))
    for k in WEIGHTS:
        if k in keys:
            add(k,forecast[k],observed[k],baseline[k])
    for label,fields in SUBTOTALS.items():
        if set(fields)<=keys:
            add(label,*(sum(values[k]*WEIGHTS[k] for k in fields)
                         for values in (forecast,observed,baseline)))
    return rows


def component_reports(detail,coverage):
    details=pd.DataFrame(detail,columns=DETAIL_FIELDS)
    days=[]
    for (day,p,timing,metric),g in details.groupby(
            ['slate_date','provider','timing_basis','metric']):
        days.append(dict(slate_date=day,provider=p,timing_basis=timing,metric=metric,
                         paired_players=len(g),source_mae=g.source_error.abs().mean(),
                         daily_mae=g.daily_error.abs().mean(),source_bias=g.source_error.mean(),
                         daily_bias=g.daily_error.mean()))
    daily=pd.DataFrame(days)
    summary=[]
    if not daily.empty:
        for (p,timing,m),g in daily.groupby(['provider','timing_basis','metric']):
            summary.append(dict(provider=p,timing_basis=timing,metric=m,dates=len(g),
                paired_players=int(g.paired_players.sum()),equal_date_source_mae=g.source_mae.mean(),
                equal_date_daily_mae=g.daily_mae.mean(),equal_date_source_bias=g.source_bias.mean(),
                equal_date_daily_bias=g.daily_bias.mean()))
    return details,daily,pd.DataFrame(summary),pd.DataFrame(coverage)
