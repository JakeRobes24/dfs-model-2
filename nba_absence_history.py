"""Historical role/absence context challenge; not a pre-lock injury forecast.

Use only earlier played rows to choose a persistent absence hypothesis.
Never choose a teammate or forecast from the target game's participation.
Evaluate on all supported target appearances, even if the teammate returns.
"""
from collections import Counter, defaultdict
from statistics import mean
from nba_component_history import FIELDS, _components, _score, _day, _number
from opportunity_evidence import teammate_participation
from slate_import import player_key

POLICIES=('four_game_mean','eight_game_mean','same_role_mean',
          'absence_minutes_only','absence_rate_only','absence_both')

def compare_absence_persistence(records, *, cutoff_day):
    cutoff=_day(cutoff_day)
    groups=defaultdict(list)
    identities=defaultdict(set)
    rejected=Counter()
    for raw in records:
        row=dict(raw)
        try:
            day=_day(row['game_date'])
            pid=str(row.get('nba_id') or '')
            team,game,source=(row.get(k) for k in ('team','game','source'))
            if (day>=cutoff or not pid.isdigit() or not isinstance(team,str) or not team
                    or not isinstance(game,str) or len(game.split('@'))!=2 or team not in game.split('@')
                    or not isinstance(source,str) or not source.startswith('https://www.nba.com/game/')):
                raise ValueError
            name=player_key(row['player'])
            if not name:
                raise ValueError
        except (ValueError,TypeError,KeyError,AttributeError):
            rejected['invalid_or_future_row']+=1
            continue
        row['game_date']=day
        row['_complete']=(_number(row.get('minutes'),10,60)
                           and all(_number(row.get(k),0,150) for k in FIELDS))
        # Identity evidence is dated, so future name conflicts or later
        # appearances cannot alter an earlier target forecast.
        identities[team,name].add((day,pid))
        groups[pid,team].append(row)
    output=[]
    for (pid,team),history in sorted(groups.items()):
        history=sorted(history,key=lambda r:r['game_date'])
        counts=Counter(r['game_date'] for r in history)
        for i in range(8,len(history)):
            target=history[i]
            prior=history[i-8:i]
            window=[*prior,target]
            if any(counts[r['game_date']]!=1 or not r['_complete'] for r in window):
                rejected['duplicate_or_incomplete_window']+=1
                continue
            role=prior[-1].get('started')
            if type(role) is not bool:
                rejected['unknown_prior_role']+=1
                continue
            same=[r for r in prior if r.get('started') is role]
            eligible=[]
            for teammate in sorted(set(prior[-1].get('teammates_absent',()))):
                if teammate==player_key(prior[-1]['player']):
                    continue
                if teammate_participation(prior[-1],teammate)!='absent':
                    continue
                # An explicit same-team identity observed before target day.
                teammate_ids={x for d,x in identities[team,teammate] if d<target['game_date']}
                if len(teammate_ids)!=1 or pid in teammate_ids:
                    continue
                left=[r for r in same if teammate_participation(r,teammate)=='played']
                right=[r for r in same if teammate_participation(r,teammate)=='absent']
                if min(len(left),len(right))<3 or min(sum(r['minutes'] for r in left),
                                                    sum(r['minutes'] for r in right))<60:
                    continue
                eligible.append((teammate,left,right))
            if len(eligible)!=1:
                rejected['no_unique_supported_absence']+=1
                continue
            teammate,left,right=eligible[0]
            four,eight,role_base,absent,actual=(_components(g,[1]*len(g))
                for g in (prior[-4:],prior,same,right,[target]))
            if any(c is None for c in (four,eight,role_base,absent,actual)):
                rejected['zero_opportunity_window']+=1
                continue
            # Shrink toward role-conditioned baseline. Do not add marginal
            # injury effects to a baseline which already includes absences.
            n=min(len(left),len(right))
            w=n/(n+5)
            blend={k:(1-w)*role_base[k]+w*absent[k] for k in role_base}
            forecasts={'four_game_mean':four,'eight_game_mean':eight,'same_role_mean':role_base,
                       'absence_minutes_only':dict(role_base,minutes=blend['minutes']),
                       'absence_rate_only':dict(blend,minutes=role_base['minutes']),
                       'absence_both':blend}
            # Target status is recorded only after prediction and never filters
            # the sample. This estimates persistence, not confirmed injury value.
            state=teammate_participation(target,teammate)
            actual_fd=_score(actual)
            for policy,c in forecasts.items():
                output.append(dict(nba_id=pid,team=team,date=target['game_date'].isoformat(),
                    source=target['source'],teammate=teammate,
                    training_dates=[r['game_date'].isoformat() for r in prior],
                    prior_role=role,target_role=target.get('started'),target_teammate_state=state,
                    with_games=len(left),without_games=len(right),policy=policy,
                    prediction=_score(c),actual=actual_fd,
                    fd_abs_error=abs(_score(c)-actual_fd),
                    minutes_abs_error=abs(c['minutes']-actual['minutes']),
                    opportunity_abs_error=abs(c['opportunity']-actual['opportunity']),
                    efficiency_abs_error=abs(c['efficiency']-actual['efficiency']),
                    peripheral_abs_error=abs(c['peripherals']-actual['peripherals'])))
    daily=[]
    by_day=defaultdict(list)
    metrics=('fd_abs_error','minutes_abs_error','opportunity_abs_error',
             'efficiency_abs_error','peripheral_abs_error')
    for r in output:
        by_day[r['date'],r['policy']].append(r)
    for (day,policy),rows in sorted(by_day.items()):
        daily.append(dict(date=day,policy=policy,players=len(rows),
                          **{k:mean(r[k] for r in rows) for k in metrics}))
    summary=[]
    for policy in POLICIES:
        rows=[r for r in daily if r['policy']==policy]
        if rows:
            summary.append(dict(policy=policy,dates=len(rows),player_games=sum(r['players'] for r in rows),
                                **{k:mean(r[k] for r in rows) for k in metrics}))
    counts=Counter(r['target_teammate_state'] for r in output if r['policy']=='four_game_mean')
    return dict(rows=output,daily=daily,summary=summary,rejected=dict(rejected),
                observed_target_teammate_states=dict(counts),certified=False,
                status='Retrospective persistent-absence hypothesis, not official pregame status or causal injury effect')
