"""Chronological history-only uncertainty benchmark; not live DFS simulation.

Use fixed eight-game historical forecasts, then compare earlier residual
distributions. Forecasts and calibration sets never read target outcomes.
Conditional on playing >=10 minutes with complete official stats. No lineup
correlation, DNP, or ownership assumptions are made.
"""
from collections import Counter,defaultdict
from statistics import mean
import math
import numpy as np
from nba_component_history import FIELDS,_day,_number,_components,_score

POLICIES=('point_residual','paired_minutes_points','paired_minutes_rate')
MIN_TRAIN=100
MIN_DATES=5
MIN_BAND=30
BANDS=(18,28)

def historical_forecasts(records,*,cutoff_day):
    cutoff=_day(cutoff_day)
    groups=defaultdict(list)
    for raw in records:
        r=dict(raw)
        try:
            day=_day(r['game_date'])
            pid=str(r.get('nba_id') or '')
            team,game,source=(r.get(k) for k in ('team','game','source'))
            if (day>=cutoff or not pid.isdigit() or not isinstance(team,str)
                or not isinstance(game,str) or len(game.split('@'))!=2
                or team not in game.split('@') or not isinstance(source,str)
                or not source.startswith('https://www.nba.com/game/')):
                continue
        except (ValueError,TypeError,KeyError):
            continue
        r['game_date']=day
        r['_complete']=(_number(r.get('minutes'),10,60)
                        and all(_number(r.get(k),0,150) for k in FIELDS))
        groups[pid,team].append(r)
    forecasts=[]
    for (pid,team),rows in sorted(groups.items()):
        counts=Counter(r['game_date'] for r in rows)
        rows=sorted(rows,key=lambda r:r['game_date'])
        for i in range(8,len(rows)):
            target=rows[i]
            past=rows[i-8:i]
            if any(counts[r['game_date']]!=1 or not r['_complete'] for r in [*past,target]):
                continue
            pred=_components(past,[1]*8)
            actual=_components([target],[1])
            if pred is None or actual is None:
                continue
            m=min(pred['minutes'],48)
            rate=pred['opportunity']*pred['efficiency']+pred['peripherals']
            if not 0<rate<=5 or not 10<=m<=48:
                continue
            forecasts.append(dict(date=target['game_date'].isoformat(),nba_id=pid,
                team=team,game=target['game'],source=target['source'],
                training_dates=[r['game_date'].isoformat() for r in past],
                minutes=m,rate=rate,fd=m*rate,actual_minutes=actual['minutes'],
                actual_fd=_score(actual)))
    return forecasts

def _residuals(rows):
    return np.asarray([(r['actual_minutes']-r['minutes'],
                       r['actual_fd']-r['fd'],
                       r['actual_fd']-r['actual_minutes']*r['rate'],
                       r['actual_fd']/r['actual_minutes']-r['rate']) for r in rows],dtype=float)

def _band(m):
    return int(np.digitize(m,BANDS))

def _interval_score(y,lo,hi):
    return hi-lo+10*max(lo-y,0)+10*max(y-hi,0)

def compare_history_ranges(records,*,cutoff_day,draws=4000,seed=42):
    if not isinstance(draws,int) or not 100<=draws<=20000:
        raise ValueError('Use 100 to 20,000 draws')
    forecasts=historical_forecasts(records,cutoff_day=cutoff_day)
    by_day=defaultdict(list)
    for r in forecasts:
        by_day[r['date']].append(r)
    prior=[]
    output=[]
    excluded=[]
    for day,targets in sorted(by_day.items()):
        if len(prior)<MIN_TRAIN or len({r['date'] for r in prior})<MIN_DATES:
            excluded.append(day)
            prior.extend(targets)
            continue
        all_errors=_residuals(prior)
        by_band={b:[r for r in prior if _band(r['minutes'])==b] for b in range(3)}
        rng=np.random.default_rng(seed+int(day.replace('-','')))
        for row in sorted(targets,key=lambda x:(x['nba_id'],x['team'])):
            cohort=by_band[_band(row['minutes'])]
            use_band=len(cohort)>=MIN_BAND and len({r['date'] for r in cohort})>=3
            errors=_residuals(cohort) if use_band else all_errors
            # Same sampled earlier observations and centered errors for all
            # policies; compare units of residual noise, not different draws.
            errors=errors-errors.mean(axis=0)
            sampled=errors[rng.integers(len(errors),size=draws)]
            sim_minutes=np.clip(row['minutes']+sampled[:,0],1/60,60)
            outcomes={
                'point_residual':row['fd']+sampled[:,1],
                'paired_minutes_points':sim_minutes*row['rate']+sampled[:,2],
                'paired_minutes_rate':sim_minutes*(row['rate']+sampled[:,3]),
            }
            for policy,values in outcomes.items():
                lo,median,hi=map(float,np.quantile(values,(.1,.5,.9)))
                y=row['actual_fd']
                output.append(dict(date=day,nba_id=row['nba_id'],team=row['team'],
                    policy=policy,training_rows=len(errors),training_dates=len({r['date'] for r in (cohort if use_band else prior)}),
                    training_latest=max(r['date'] for r in (cohort if use_band else prior)),
                    band_fallback=not use_band,p10=lo,p50=median,p90=hi,actual=y,
                    covered=float(lo<=y<=hi),below=float(y<lo),above=float(y>hi),
                    width=hi-lo,interval_score=_interval_score(y,lo,hi),
                    median_error=abs(median-y),baseline_error=abs(row['fd']-y)))
        prior.extend(targets)
    metrics=('covered','below','above','width','interval_score','median_error','baseline_error')
    daily=[]
    groups=defaultdict(list)
    for r in output:
        groups[r['date'],r['policy']].append(r)
    for (day,p),rows in sorted(groups.items()):
        daily.append(dict(date=day,policy=p,players=len(rows),**{k:mean(r[k] for r in rows) for k in metrics}))
    summary=[]
    for p in POLICIES:
        rows=[r for r in daily if r['policy']==p]
        if rows:
            summary.append(dict(policy=p,dates=len(rows),player_games=sum(r['players'] for r in rows),
                                **{k:mean(r[k] for r in rows) for k in metrics}))
    return dict(summary=summary,daily=daily,rows=output,forecast_rows=len(forecasts),
                warmup_dates=excluded,certified=False,
                status='Retrospective history-only conditional-on-playing ranges; not DAILY or live DFS calibration')
