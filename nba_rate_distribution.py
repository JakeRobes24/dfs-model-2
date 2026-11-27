"""Matched historical NBA minute/rate distribution challengers; research only."""
from collections import Counter, defaultdict
from datetime import date
from statistics import mean
import math
import numpy as np

WEIGHTS = {'points':1, 'reboundsTotal':1.2, 'assists':1.5, 'steals':3, 'blocks':3, 'turnovers':-1}


def score_draws(draws, actual):
    x = np.sort(np.asarray(draws, dtype=float) - actual)
    n = len(x)
    crps = np.abs(x).mean() - np.mean((2*np.arange(n)-n+1)/n*x)
    lo, hi = np.quantile(x, [.1,.9])
    low, high = max(0.,lo), max(0.,-hi)
    return dict(crps=float(max(0.,crps)), coverage=float(lo<=0<=hi),
                width=float(hi-lo), interval_score=float(hi-lo+10*(low+high)),
                lower_miss=float(lo>0), upper_miss=float(hi<0),
                bias=float(x.mean()), mean_abs_error=float(abs(x.mean())),
                lower_excess=float(lo), upper_excess=float(-hi))


def compare_rate_distributions(records, *, cutoff_day):
    cutoff = date.fromisoformat(cutoff_day)
    groups = defaultdict(list)
    for r in records:
        try:
            day = date.fromisoformat(r['game_date'])
            pid, team, game = str(r['nba_id']), r['team'], r['game']
            if (day>=cutoff or not pid.isdigit() or not team or len(game.split('@'))!=2
                    or team not in game.split('@') or not r['source'].startswith('https://www.nba.com/game/')):
                continue
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        valid = all(type(r.get(k)) in (int,float) and math.isfinite(r[k]) and 0<=r[k]<=150
                    for k in (*WEIGHTS,'fieldGoalsAttempted','freeThrowsAttempted'))
        m = r.get('minutes')
        valid = valid and type(m) in (int,float) and math.isfinite(m) and 10<=m<=60
        value = (float(m),sum(r[k]*w for k,w in WEIGHTS.items()),
                 r['fieldGoalsAttempted']+.44*r['freeThrowsAttempted']+r['turnovers']) if valid else None
        groups[pid,team].append((day,value))
    detail = []
    for (pid,team), history in sorted(groups.items()):
        counts = Counter(d for d,_ in history)
        history.sort(key=lambda r:r[0])
        for n in (8,12):
            for i in range(n,len(history)):
                window = history[i-n:i+1]
                if any(counts[d]!=1 or v is None for d,v in window):
                    continue
                prior, target = window[:-1],window[-1]
                # Match the existing component benchmark's nonzero opportunity gate.
                if target[1][2]<=0 or any(sum(v[2] for _,v in prior[-k:])<=0 for k in (2,4,8,n)):
                    continue
                minutes, points, _ = np.array([v for _,v in prior]).T
                rates = points/minutes
                paired = points
                independent = np.multiply.outer(minutes,rates).ravel()
                # Center both on the same existing historical mean, isolating distribution shape.
                centered = independent-independent.mean()+paired.mean()
                for policy,draws in [('paired',paired),('independent',independent),('independent_centered',centered)]:
                    detail.append(dict(cohort=n, date=target[0].isoformat(), nba_id=pid, team=team,
                                       policy=policy, **score_draws(draws,target[1][1])))
    by_date=defaultdict(list)
    for r in detail:
        by_date[r['cohort'],r['policy'],r['date']].append(r)
    metrics=('crps','coverage','width','interval_score','lower_miss','upper_miss','bias','mean_abs_error')
    by_policy=defaultdict(list)
    for (n,p,d),rs in sorted(by_date.items()):
        by_policy[n,p].append(dict(players=len(rs),**{k:mean(r[k] for r in rs) for k in metrics}))
    summary=[dict(cohort=n,policy=p,dates=len(rs),player_games=sum(r['players'] for r in rs),
                  **{k:mean(r[k] for r in rs) for k in metrics}) for (n,p),rs in sorted(by_policy.items())]
    return dict(summary=summary,rows=detail,certified=False)


def calibrate_rate_ranges(rows, *, minimum_prior_rows=100):
    """Earlier-date calibration of central 80% intervals, with matched evaluation dates."""
    if type(minimum_prior_rows) is not int or minimum_prior_rows<1:
        raise ValueError('Minimum prior rows must be a positive integer.')
    groups=defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[r['cohort'],r['policy']][r['date']].append(r)
    daily=[]
    for (n,p),dates in sorted(groups.items()):
        past=[]
        for day,batch in sorted(dates.items()):
            if len(past)>=minimum_prior_rows:
                i=min(len(past)-1,math.ceil(.8*(len(past)+1))-1)
                padding=max(0.,float(np.partition(past,i)[i]))
                for method,added in [('original',0.),('earlier_date',padding)]:
                    scores=[]
                    for r in batch:
                        low,high=r['lower_excess']-added,r['upper_excess']-added
                        width=r['width']+2*added
                        scores.append(dict(coverage=float(low<=0 and high<=0),width=width,
                                           interval_score=width+10*(max(0.,low)+max(0.,high))))
                    daily.append(dict(cohort=n,policy=p,date=day,method=method,players=len(batch),
                                      padding=added,**{k:mean(s[k] for s in scores) for k in scores[0]}))
            past.extend(max(r['lower_excess'],r['upper_excess']) for r in batch)
    by_policy=defaultdict(list)
    for r in daily:
        by_policy[r['cohort'],r['policy'],r['method']].append(r)
    return [dict(cohort=n,policy=p,method=m,dates=len(rs),player_games=sum(r['players'] for r in rs),
                 **{k:mean(r[k] for r in rs) for k in ('coverage','width','interval_score')})
            for (n,p,m),rs in sorted(by_policy.items())]
