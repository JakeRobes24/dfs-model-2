"""Chronological conditional played-player distribution shape comparison."""
from collections import defaultdict, Counter
from datetime import date, timedelta
import math
import numpy as np

WEIGHTS={'points':1,'reboundsTotal':1.2,'assists':1.5,'steals':3,'blocks':3,'turnovers':-1}
POLICIES=('personal','half_pooled','pooled')


def score(draws,actual):
    x=np.sort(np.asarray(draws,dtype=float)-actual)
    n=len(x)
    lo,hi=np.quantile(x,[.1,.9])
    width=hi-lo
    return dict(crps=float(max(0.,np.abs(x).mean()-np.mean((2*np.arange(n)-n+1)*x/n))),
                coverage=float(lo<=0<=hi),width=float(width),
                interval_score=float(width+10*(max(lo,0)+max(-hi,0))),
                lower_miss=float(lo>0),upper_miss=float(hi<0),mean_bias=float(x.mean()))


def compare(records,cutoff,minimum_rows=100,minimum_dates=3):
    """Fixed four-game centers; pooled shape uses only earlier residuals.

    This is a played-only history benchmark, not live distribution calibration.
    A short prior played appearance is retained, not converted to a DNP.
    """
    if (type(cutoff) is not date or type(minimum_rows) is not int or minimum_rows<1
            or type(minimum_dates) is not int or minimum_dates<1):
        raise ValueError('Exact cutoff and positive minimums required')
    groups=defaultdict(list)
    for r in records:
        try:
            day=date.fromisoformat(str(r['game_date'])[:10])
            pid=str(r['nba_id'])
            team,game=r['team'],r['game']
            if (day>=cutoff or not pid.isdigit() or not team or len(game.split('@'))!=2
                    or len(set(game.split('@')))!=2 or team not in game.split('@')
                    or not r['source'].startswith('https://www.nba.com/game/')):
                continue
        except (KeyError,TypeError,ValueError,AttributeError):
            continue
        m=r.get('minutes')
        good=(type(m) in (int,float) and math.isfinite(m) and 0<m<=60
              and all(type(r.get(k)) in (int,float) and math.isfinite(r[k])
                      and 0<=r[k]<=150 for k in WEIGHTS))
        groups[pid,team].append((day,(m,sum(r[k]*v for k,v in WEIGHTS.items())) if good else None))
    by_day=defaultdict(list)
    for (pid,team),hist in sorted(groups.items()):
        hist.sort(key=lambda x:x[0])
        count=Counter(d for d,_ in hist)
        for i in range(4,len(hist)):
            window=hist[i-4:i+1]
            day=window[-1][0]
            if (any(count[d]!=1 or v is None for d,v in window)
                or day-window[0][0]>timedelta(days=30)
                or day-window[-2][0]>timedelta(days=7)):
                continue
            m,p=np.array([v for _,v in window[:-1]]).T
            actual_m,actual=window[-1][1]
            center=p.mean()
            scale=math.sqrt(m.mean())
            by_day[day].append(dict(date=day.isoformat(),nba_id=pid,team=team,actual=actual,
                actual_minutes=actual_m,center=center,minutes=m.mean(),short_prior=bool(m.min()<10),
                points=p,scale=scale,residual=(actual-center)/scale))
    past=[]
    past_dates=0
    out=[]
    for day,batch in sorted(by_day.items()):
        if len(past)>=minimum_rows and past_dates>=minimum_dates:
            # Equal-weight deterministic empirical quantiles. Center them to
            # zero so every policy preserves the same personal mean.
            pool=np.quantile(past,(np.arange(128)+.5)/128)
            pool=pool-pool.mean()
            for r in batch:
                personal=np.repeat(r['points'],32)
                pooled=r['center']+r['scale']*pool
                for policy,draws in [('personal',personal),
                                    ('half_pooled',np.concatenate([personal,pooled])),
                                    ('pooled',pooled)]:
                    out.append(dict(**{k:v for k,v in r.items() if k not in ('points','scale','residual')},
                        policy=policy,earlier_rows=len(past),earlier_dates=past_dates,
                        **score(draws,r['actual'])))
        past.extend(r['residual'] for r in batch)
        past_dates+=1
    return out
