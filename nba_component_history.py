"""Chronological NBA history-only production benchmark (no live scoring).

Predict the next observed played game from four earlier complete official
box-score rows of the same player/team. No target-day starter, minutes,
participation, usage or outcome enters prediction. Conditional on playing
and having complete stats; not a full-slate DFS forecast or DAILY comparison.
"""
from collections import Counter, defaultdict
from datetime import date
from math import isfinite
from statistics import mean
from opportunity_evidence import FD_WEIGHTS, OPPORTUNITY_WEIGHTS

FIELDS = set(FD_WEIGHTS) | set(OPPORTUNITY_WEIGHTS)
POLICIES = ('last_game','four_game_mean','recent_weighted',
            'equal_minutes_recent_components','recent_minutes_equal_components',
            'equal_minutes_recent_opportunity','equal_minutes_recent_efficiency',
            'equal_minutes_recent_peripherals','persistent_role_prior')
EQUAL = (1,1,1,1)
RECENT = (1,2,3,4)

def _day(value):
    if type(value) is date:
        return value
    return date.fromisoformat(value)

def _number(v,lo,hi):
    return type(v) in (float,int) and isfinite(v) and lo<=v<=hi

def _components(rows, weights):
    minutes=sum(r['minutes']*w for r,w in zip(rows,weights))
    opp=sum(sum(r[k]*v for k,v in OPPORTUNITY_WEIGHTS.items())*w for r,w in zip(rows,weights))
    net=sum((r['points']-r['turnovers'])*w for r,w in zip(rows,weights))
    per=sum(sum(r[k]*v for k,v in FD_WEIGHTS.items() if k not in {'points','turnovers'})*w for r,w in zip(rows,weights))
    if not minutes or not opp:
        return None
    return dict(minutes=minutes/sum(weights),opportunity=opp/minutes,
                efficiency=net/opp,peripherals=per/minutes)

def _score(c):
    return c['minutes']*(c['opportunity']*c['efficiency']+c['peripherals'])

def _forecast(prior):
    equal,recent,last=(_components(prior,w) for w in (EQUAL,RECENT,(0,0,0,1)))
    if any(c is None for c in (equal,recent,last)):
        return None
    role=prior[-1].get('started')
    role_rows=[r for r in prior if type(role) is bool and r.get('started') is role]
    # A fixed history-only persistent-role prior, not a confirmed target role.
    # Shrink the role sample toward the four-game baseline, using the same
    # role mix across all components; no role evidence falls back to equal.
    role_prior=equal.copy()
    if len(role_rows)>=2:
        c=_components(role_rows,[1]*len(role_rows))
        if c is not None:
            w=len(role_rows)/(len(role_rows)+4)
            role_prior={k:(1-w)*equal[k]+w*c[k] for k in equal}
    forecasts={
        'last_game':last,'four_game_mean':equal,'recent_weighted':recent,
        'equal_minutes_recent_components':dict(recent,minutes=equal['minutes']),
        'recent_minutes_equal_components':dict(equal,minutes=recent['minutes']),
        'equal_minutes_recent_opportunity':dict(equal,opportunity=recent['opportunity']),
        'equal_minutes_recent_efficiency':dict(equal,efficiency=recent['efficiency']),
        'equal_minutes_recent_peripherals':dict(equal,peripherals=recent['peripherals']),
        'persistent_role_prior':role_prior,
    }
    return forecasts,role

def compare_component_history(records, *, cutoff_day):
    cutoff=_day(cutoff_day)
    groups=defaultdict(list)
    rejected=Counter()
    for raw in records:
        row=dict(raw)
        try:
            day=_day(row['game_date'])
            if day>=cutoff:
                rejected['on_or_after_cutoff']+=1
                continue
            pid=str(row.get('nba_id') or '')
            team=row.get('team')
            game=row.get('game')
            source=row.get('source')
            if (not pid.isdigit() or not isinstance(team,str) or not team
                    or not isinstance(game,str) or len(game.split('@'))!=2
                    or team not in game.split('@') or not isinstance(source,str)
                    or not source.startswith('https://www.nba.com/game/')):
                raise ValueError('identity/provenance')
        except (ValueError,TypeError,KeyError):
            rejected['identity_or_provenance']+=1
            continue
        row['game_date']=day
        # Keep incomplete rows in chronology so a missing intermediate played
        # game cannot silently turn a four-game window into a different sample.
        row['_complete']=(_number(row.get('minutes'),10,60)
                           and all(_number(row.get(k),0,150) for k in FIELDS))
        groups[(pid,team)].append(row)
    output=[]
    for (pid,team),history in sorted(groups.items()):
        counts=Counter(r['game_date'] for r in history)
        history=sorted(history,key=lambda r:r['game_date'])
        for i in range(4,len(history)):
            target=history[i]
            prior=history[i-4:i]
            window=[*prior,target]
            if any(counts[r['game_date']]!=1 for r in window):
                rejected['duplicate_date_window']+=1
                continue
            if not all(r['_complete'] for r in window):
                rejected['incomplete_or_short_window']+=1
                continue
            result=_forecast(prior)
            actual=_components([target],[1])
            if result is None or actual is None:
                rejected['zero_opportunity_window']+=1
                continue
            predictions,role=result
            actual_fd=_score(actual)
            for policy,c in predictions.items():
                output.append(dict(nba_id=pid,team=team,date=target['game_date'].isoformat(),
                    game=target['game'],source=target['source'],
                    training_dates=[r['game_date'].isoformat() for r in prior],
                    policy=policy,predicted_fd=_score(c),actual_fd=actual_fd,
                    fd_abs_error=abs(_score(c)-actual_fd),
                    minutes_abs_error=abs(c['minutes']-actual['minutes']),
                    opportunity_abs_error=abs(c['opportunity']-actual['opportunity']),
                    efficiency_abs_error=abs(c['efficiency']-actual['efficiency']),
                    peripheral_abs_error=abs(c['peripherals']-actual['peripherals']),
                    last_known_role=role,actual_role=target.get('started')))
    # Equal date weight, plus raw player-game counts. Do not treat repeated
    # players, shared teams, or overlapping training windows as independent.
    daily=[]
    metrics=('fd_abs_error','minutes_abs_error','opportunity_abs_error',
             'efficiency_abs_error','peripheral_abs_error')
    by_day=defaultdict(list)
    for r in output:
        by_day[(r['date'],r['policy'])].append(r)
    for (day,policy),group in sorted(by_day.items()):
        daily.append(dict(date=day,policy=policy,players=len(group),
                          **{k:mean(r[k] for r in group) for k in metrics}))
    summary=[]
    for policy in POLICIES:
        subset=[r for r in daily if r['policy']==policy]
        if subset:
            summary.append(dict(policy=policy,dates=len(subset),
                player_games=sum(r['players'] for r in subset),
                **{k:mean(r[k] for r in subset) for k in metrics}))
    return dict(rows=output,daily=daily,summary=summary,rejected=dict(rejected),
                status='Retrospective history-only, played complete windows; no prelock role or DAILY comparison',
                certified=False)
