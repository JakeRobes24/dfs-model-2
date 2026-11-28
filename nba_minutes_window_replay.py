"""Historical NBA minutes sensitivity, including short played appearances.

Research only. Observed games are not a complete team schedule. Explicit
prior absence is not proof of injury or a confirmed target-game return.
"""
from collections import Counter,defaultdict
from datetime import date,timedelta
from statistics import mean,median
from math import isfinite
from slate_import import player_key
from opportunity_evidence import FD_WEIGHTS

def compare_minutes_windows(records,cutoff):
    if type(cutoff) is not date:
        raise ValueError('Exact cutoff date required')
    histories=defaultdict(list)
    team_games=defaultdict(list)
    for raw in records:
        try:
            day=date.fromisoformat(str(raw['game_date'])[:10])
            pid=str(raw['nba_id'])
            team=raw['team']
            game=raw['game']
            if (not pid.isdigit() or not player_key(raw['player']) or
                not isinstance(team,str) or not team or not isinstance(game,str)
                or len(game.split('@'))!=2 or len(set(game.split('@')))!=2
                or team not in game.split('@') or not raw['source'].startswith('https://www.nba.com/game/')):
                continue
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
        if day>=cutoff:
            continue
        row=dict(raw,day=day)
        histories[pid,team].append(row)
        team_games[team,day].append(row)
    team_days=defaultdict(list)
    for team,day in team_games:
        team_days[team].append(day)
    for days in team_days.values():
        days.sort()
    def valid_minutes(r):
        m=r.get('minutes')
        return type(m) in (int,float) and isfinite(m) and 0<m<=60
    def complete(r):
        return valid_minutes(r) and all(type(r.get(k)) in (int,float) and 0<=r[k]<=150 for k in FD_WEIGHTS)
    def fd(r):
        return sum(r[k]*w for k,w in FD_WEIGHTS.items())
    output=[]
    for (pid,team),rs in sorted(histories.items()):
        rs.sort(key=lambda x:x['day'])
        counts=Counter(r['day'] for r in rs)
        for i in range(4,len(rs)):
            prior,target=rs[i-4:i],rs[i]
            day=target['day']
            if (day-prior[0]['day']>timedelta(days=30) or day-prior[-1]['day']>timedelta(days=7)
                or any(counts[r['day']]!=1 or not complete(r) for r in [*prior,target])):
                continue
            m=[r['minutes'] for r in prior]
            avg=mean(m)
            med=median(m)
            earlier=[d for d in team_days[team] if d<day]
            absent=False
            if earlier and earlier[-1]>prior[-1]['day']:
                rows=team_games[team,earlier[-1]]
                name=player_key(prior[-1]['player'])
                absent=bool(rows) and all(name in (r.get('teammates_absent') or ())
                        and name not in (r.get('teammates_played') or ()) for r in rows)
            row=dict(date=day.isoformat(),nba_id=pid,team=team,
                actual_minutes=target['minutes'],actual_fd=fd(target),
                rate=sum(fd(r) for r in prior)/sum(m),short_prior=min(m)<10,
                explicit_prior_absence=absent,latest_age=(day-prior[-1]['day']).days,
                mean4=avg,median4=med,half_median=(avg+med)/2,
                weighted4=sum(x*w for x,w in zip(m,(1,2,3,4)))/10,mean2=mean(m[-2:]))
            if i>=8:
                long=rs[i-8:i]
                if day-long[0]['day']<=timedelta(days=30) and all(
                        counts[r['day']]==1 and valid_minutes(r) for r in long):
                    row.update(mean8=mean(r['minutes'] for r in long),
                               median8=median(r['minutes'] for r in long))
                    row['half_mean8']=(row['mean8']+avg)/2
            output.append(row)
    return output
