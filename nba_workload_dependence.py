"""History-only workload-conditioned NBA dependence experiment."""
from collections import defaultdict
from datetime import date
from itertools import combinations
from math import isfinite,sqrt
from statistics import mean
import numpy as np
from nba_group_dependence import normal_scores

POLICIES=('independent','aggregate','workload')


def _band(r):
    return int(r['minutes']>=25)


def _relationship(a,b):
    return ('same' if a['team']==b['team'] else 'opp',tuple(sorted((_band(a),_band(b)))))


def _games(rows):
    groups=defaultdict(list)
    for r in rows:
        groups[r['date'],r['game']].append(r)
    for (day,game),players in groups.items():
        if set(r['team'] for r in players)==set(game.split('@')) and len({r['id'] for r in players})==len(players):
            yield day,game,players


def _fit(prior):
    errors={b:[r['actual']-r['center'] for r in prior if _band(r)==b] for b in (0,1)}
    if any(not x or np.std(x)<=0 for x in errors.values()):
        return None
    mu={b:mean(x) for b,x in errors.items()}
    sd={b:float(np.std(x)) for b,x in errors.items()}
    games=defaultdict(list)
    for day,_,players in _games(prior):
        products=defaultdict(list)
        for a,b in combinations(players,2):
            k=_relationship(a,b)
            z=lambda r:(r['actual']-r['center']-mu[_band(r)])/sd[_band(r)]
            v=z(a)*z(b)
            products[k].append(v)
            products[k[0]].append(v)
        for k,values in products.items():
            games[k].append((day,mean(values)))
    coeff={}
    for k,values in games.items():
        days=defaultdict(list)
        for day,v in values:
            days[day].append(v)
        n=len(values)
        coeff[k]=float(np.clip(mean(mean(v) for v in days.values())*n/(n+50),-.35,.35)) if n>=20 and len(days)>=3 else 0.
    return sd,coeff


def _score(players,sd,coeff,policy):
    s=np.array([sd[_band(r)] for r in players])
    c=np.eye(len(players))
    for i,j in combinations(range(len(players)),2):
        k=_relationship(players[i],players[j])
        c[i,j]=c[j,i]=0. if policy=='independent' else coeff.get(k[0] if policy=='aggregate' else k,0.)
    low=np.linalg.eigvalsh(c)[0]
    if low<.01:
        c=np.eye(len(players))+(c-np.eye(len(players)))*.99/(1-low)
    return normal_scores(sum(r['actual'] for r in players),
                         sum(r['center'] for r in players),sqrt(float(s@c@s)))


def compare_workload_dependence(records):
    """Require reconciled historical forecasts, not a current slate or full simulation.
    
    Groups selected only by projected workload within the played evaluation
    cohort. 25-minute bands are not confirmed starter roles. Fit on earlier
    dates; unsupported relationship uses zero. Keep centers and marginal
    scales identical. No automatic correlation or scoring adjustment.
    """
    seen=set()
    days=defaultdict(list)
    for r in records:
        d=date.fromisoformat(r['date'])
        pid=r.get('id')
        game=r.get('game')
        if (not isinstance(pid,str) or not pid.strip() or (d,pid) in seen
                or not isinstance(game,str) or len(game.split('@'))!=2
                or len(set(game.split('@')))!=2 or r.get('team') not in game.split('@')):
            raise ValueError('Require unique dated player identity and oriented game')
        if not all(type(r.get(k)) in (int,float) and isfinite(r[k]) for k in ('minutes','center','actual')) or not 0<r['minutes']<=60:
            raise ValueError('Require finite matched history forecasts')
        seen.add((d,pid))
        days[d].append(r)
    prior=[]
    output=[]
    for day,targets in sorted(days.items()):
        fit=_fit(prior) if len(prior)>=100 and len({r['date'] for r in prior})>=3 else None
        if fit is not None:
            sd,coeff=fit
            for _,game,p in _games(targets):
                groups=[]
                for team in sorted({r['team'] for r in p}):
                    q=sorted((r for r in p if r['team']==team),key=lambda r:(-r['minutes'],r['id']))
                    if len(q)>=2:
                        groups.append(('top2_same',q[:2]))
                    hi=[r for r in q if _band(r)]
                    lo=[r for r in q if not _band(r) and r['minutes']>=10]
                    if hi and lo:
                        groups.append(('mixed_same',[hi[0],lo[0]]))
                mixed=[ps for kind,ps in groups if kind=='mixed_same']
                if len(mixed)==2:
                    groups.append(('mixed_four',mixed[0]+mixed[1]))
                for kind,players in groups:
                    for policy in POLICIES:
                        output.append(dict(date=day.isoformat(),game=game,kind=kind,
                            policy=policy,players=[r['id'] for r in players],
                            **_score(players,sd,coeff,policy)))
        prior.extend(targets)
    return output
