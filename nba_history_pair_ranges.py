"""History-only same-game residual dependence benchmark, not live DFS scoring.

Chronological earlier eight-game forecasts, conditional on playing >=10 min.
Estimate a shrunk relationship-specific residual correlation using earlier
games. Test pair-total uncertainty against independent sampling on identical
held-out pairs. Pair totals are diagnostics, not nine-player contest entries.
"""
from collections import defaultdict
from itertools import combinations
from statistics import mean
import numpy as np
from nba_history_ranges import historical_forecasts, _band, _interval_score

RELATIONSHIPS=('teammate','opponent')
MIN_DATES=5
MIN_GAMES=20
MIN_ROWS=100
MIN_BAND=30
POLICIES=('independent','shrunk_dependence')

def _fit(rows):
    errors=np.array([r['actual_fd']-r['fd'] for r in rows],dtype=float)
    fallback=(float(errors.mean()),float(errors.std()))
    if fallback[1]<=0:
        return None
    cohorts={}
    for b in range(3):
        values=errors[np.array([_band(r['minutes'])==b for r in rows])]
        cohorts[b]=(float(values.mean()),float(values.std())) if len(values)>=MIN_BAND and values.std()>0 else fallback
    return cohorts

def _games(rows):
    groups=defaultdict(list)
    for r in rows:
        groups[r['date'],r['game']].append(r)
    return [(k,sorted(g,key=lambda r:(r['team'],r['nba_id']))) for k,g in sorted(groups.items())
            if len({r['nba_id'] for r in g})==len(g) and len({r['team'] for r in g})==2]

def _pairs(group):
    for a,b in combinations(group,2):
        yield ('teammate' if a['team']==b['team'] else 'opponent'),a,b

def _fit_dependence(prior, scale):
    # Per-game estimates with equal date/game weighting; standardized residual
    # cross-products are only correlation proxies. Cap and shrink explicitly.
    per_relation=defaultdict(list)
    for (day,game),group in _games(prior):
        products=defaultdict(list)
        for rel,a,b in _pairs(group):
            def z(r):
                mu,sd=scale[_band(r['minutes'])]
                return (r['actual_fd']-r['fd']-mu)/sd
            products[rel].append(z(a)*z(b))
        for rel,values in products.items():
            per_relation[rel].append((day,mean(values)))
    result={}
    for rel in RELATIONSHIPS:
        rows=per_relation[rel]
        dates=len({d for d,_ in rows})
        if len(rows)<MIN_GAMES or dates<MIN_DATES:
            return None
        by_day=defaultdict(list)
        for d,v in rows:
            by_day[d].append(v)
        raw=mean(mean(v) for v in by_day.values())
        rho=float(np.clip(raw*len(rows)/(len(rows)+50),-.35,.35))
        result[rel]=dict(rho=rho,raw=raw,dates=dates,games=len(rows))
    return result

def compare_pair_ranges(records,*,cutoff_day,draws=2000,seed=42):
    if not isinstance(draws,int) or not 100<=draws<=20000:
        raise ValueError('Use 100 to 20,000 draws')
    forecasts=historical_forecasts(records,cutoff_day=cutoff_day)
    dates=defaultdict(list)
    for r in forecasts:
        dates[r['date']].append(r)
    prior=[]
    detail=[]
    fits=[]
    for day,targets in sorted(dates.items()):
        if len(prior)<MIN_ROWS or len({r['date'] for r in prior})<MIN_DATES:
            prior.extend(targets)
            continue
        scale=_fit(prior)
        fit=_fit_dependence(prior,scale) if scale else None
        if fit is None:
            prior.extend(targets)
            continue
        fits.append(dict(date=day,training_latest=max(r['date'] for r in prior),**fit))
        rng=np.random.default_rng(seed+int(day.replace('-','')))
        for (_,game),group in _games(targets):
            for rel,a,b in _pairs(group):
                # Normal marginal comparison isolates dependence from changes
                # in marginal distributions. Same underlying draws per pair.
                x,y=rng.standard_normal((2,draws))
                _,sa=scale[_band(a['minutes'])]
                _,sb=scale[_band(b['minutes'])]
                total=a['fd']+b['fd']
                actual=a['actual_fd']+b['actual_fd']
                for policy in POLICIES:
                    rho=fit[rel]['rho'] if policy=='shrunk_dependence' else 0.
                    values=total+sa*x+sb*(rho*x+np.sqrt(1-rho*rho)*y)
                    lo,hi=map(float,np.quantile(values,(.1,.9)))
                    detail.append(dict(date=day,game=game,relationship=rel,
                        players=[a['nba_id'],b['nba_id']],policy=policy,rho=rho,
                        actual=actual,p10=lo,p90=hi,covered=float(lo<=actual<=hi),
                        width=hi-lo,interval_score=_interval_score(actual,lo,hi)))
        prior.extend(targets)
    metrics=('covered','width','interval_score')
    groups=defaultdict(list)
    for r in detail:
        groups[r['date'],r['game'],r['relationship'],r['policy']].append(r)
    game_rows=[]
    for (d,g,rel,p),rows in sorted(groups.items()):
        game_rows.append(dict(date=d,game=g,relationship=rel,policy=p,pairs=len(rows),
                              **{k:mean(r[k] for r in rows) for k in metrics}))
    daily=[]
    by_day=defaultdict(list)
    for r in game_rows:
        by_day[r['date'],r['relationship'],r['policy']].append(r)
    for (d,rel,p),rows in sorted(by_day.items()):
        daily.append(dict(date=d,relationship=rel,policy=p,games=len(rows),
                          pairs=sum(r['pairs'] for r in rows),
                          **{k:mean(r[k] for r in rows) for k in metrics}))
    summary=[]
    for rel in RELATIONSHIPS:
        for p in POLICIES:
            rows=[r for r in daily if r['relationship']==rel and r['policy']==p]
            if rows:
                summary.append(dict(relationship=rel,policy=p,dates=len(rows),
                    games=sum(r['games'] for r in rows),pairs=sum(r['pairs'] for r in rows),
                    **{k:mean(r[k] for r in rows) for k in metrics}))
    return dict(summary=summary,daily=daily,game_rows=game_rows,rows=detail,fits=fits,
                certified=False,status='Retrospective history-only normal pair ranges; repeated pairs are not independent; no full-lineup or live DFS correlation calibration')
