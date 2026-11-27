"""History-only same-game group uncertainty; never alters scoring or roster selection."""
from collections import defaultdict
from itertools import combinations
from math import erf, exp, pi, sqrt
from statistics import mean, NormalDist
import numpy as np

Z80 = NormalDist().inv_cdf(.9)


def correlation_matrix(teams, same, opposite):
    """Shrink toward identity if a relationship matrix is not positive definite."""
    n = len(teams)
    c = np.eye(n)
    for i, j in combinations(range(n), 2):
        c[i,j] = c[j,i] = same if teams[i] == teams[j] else opposite
    minimum = np.linalg.eigvalsh(c)[0]
    if minimum < .01:
        c = np.eye(n) + (c-np.eye(n)) * (.99/(1-minimum))
    return c


def game_groups(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r['date'],r['game']].append(r)
    return [g for g in groups.values() if len({r['nba_id'] for r in g})==len(g)
            and len({r['team'] for r in g})==2]


def _band(row):
    return int(np.digitize(row['minutes'], [18,28]))


def fit(prior):
    errors = np.array([r['actual_fd']-r['fd'] for r in prior])
    fallback = (errors.mean(),errors.std())
    if fallback[1] <= 0:
        return None
    bands = {}
    for b in range(3):
        e = errors[np.array([_band(r)==b for r in prior])]
        bands[b] = (e.mean(),e.std()) if len(e)>=30 and e.std()>0 else fallback
    by_date = defaultdict(list)
    for game in game_groups(prior):
        pairs = defaultdict(list)
        for a,b in combinations(game,2):
            def z(r):
                mu,sd = bands[_band(r)]
                return (r['actual_fd']-r['fd']-mu)/sd
            pairs[a['team']==b['team']].append(z(a)*z(b))
        if True in pairs and False in pairs:
            by_date[game[0]['date']].append([mean(pairs[True]),mean(pairs[False])])
    games = sum(map(len,by_date.values()))
    if games<20 or len(by_date)<5:
        return None
    rho = np.clip(np.mean([np.mean(v,axis=0) for v in by_date.values()],axis=0)*games/(games+50),-.35,.35)
    return bands,rho,games


def normal_scores(actual, center, sd):
    z = (actual-center)/sd
    crps = sd*(z*erf(z/sqrt(2))+sqrt(2/pi)*exp(-z*z/2)-1/sqrt(pi))
    half = Z80*sd
    return dict(crps=crps, coverage=float(abs(actual-center)<=half),width=2*half,
                interval_score=2*half+10*max(0.,abs(actual-center)-half))


def compare_groups(forecasts):
    """Select two highest forecast-minute players per club; compare same four players.

    Played-only candidate pool, no selection by actual performance. No actual
    contest lineup or DNP validation. Learn residual relationships from earlier dates.
    """
    days = defaultdict(list)
    for r in forecasts:
        days[r['date']].append(r)
    prior,rows = [],[]
    for day,targets in sorted(days.items()):
        trained = fit(prior) if len(prior)>=100 else None
        if trained is not None:
            bands,rho,games = trained
            for group in game_groups(targets):
                teams = sorted({r['team'] for r in group})
                selected = [sorted([r for r in group if r['team']==t],key=lambda r:(-r['minutes'],r['nba_id']))[:2] for t in teams]
                if any(len(g)!=2 for g in selected):
                    continue
                for kind, players in [('four_same_game', selected[0]+selected[1]), *[('two_teammates',g) for g in selected]]:
                    center = sum(r['fd'] for r in players)
                    actual = sum(r['actual_fd'] for r in players)
                    sd = np.array([bands[_band(r)][1] for r in players])
                    for policy in ('independent','shrunk_dependence'):
                        corr = correlation_matrix([r['team'] for r in players],*(rho if policy=='shrunk_dependence' else (0.,0.)))
                        total_sd = sqrt(float(sd@corr@sd))
                        rows.append(dict(date=day,game=group[0]['game'],kind=kind,policy=policy,
                                         players=[r['nba_id'] for r in players],training_latest=max(r['date'] for r in prior),
                                         training_games=games,center=center,actual=actual,**normal_scores(actual,center,total_sd)))
        prior.extend(targets)
    metrics=('crps','coverage','width','interval_score')
    daily=defaultdict(list)
    for r in rows:
        daily[r['kind'],r['policy'],r['date']].append(r)
    by_policy=defaultdict(list)
    for (kind,policy,day),g in sorted(daily.items()):
        by_policy[kind,policy].append(dict(groups=len(g),**{k:mean(r[k] for r in g) for k in metrics}))
    summary=[dict(kind=kind,policy=policy,dates=len(g),groups=sum(r['groups'] for r in g),
                  **{k:mean(r[k] for r in g) for k in metrics}) for (kind,policy),g in sorted(by_policy.items())]
    return dict(rows=rows,summary=summary,certified=False)
