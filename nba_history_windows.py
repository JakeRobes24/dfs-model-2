"""Compare recent and longer history windows on identical future appearances.

No target minutes or role is used to form predictions. Fixed windows declared
Nov26; retrospective, conditional on playing, not a live DFS scoring policy.
"""
from collections import Counter,defaultdict
from statistics import mean
from nba_component_history import FIELDS,_day,_number,_components,_score

COHORTS=(8,12)
METRICS=('fd_abs_error','minutes_abs_error','opportunity_abs_error',
         'efficiency_abs_error','peripheral_abs_error','fppm_abs_error',
         'fppm_bias','minutes_bias','fd_bias','minutes_effect','rate_effect')

def compare_history_windows(records, *, cutoff_day, short_long_challenge=False,
                            rate_challenge=False):
    cutoff=_day(cutoff_day)
    groups=defaultdict(list)
    rejected=Counter()
    for raw in records:
        r=dict(raw)
        try:
            day=_day(r['game_date'])
            pid=str(r.get('nba_id') or '')
            team,game,source=(r.get(k) for k in ('team','game','source'))
            if (day>=cutoff or not pid.isdigit() or not isinstance(team,str) or not team
                    or not isinstance(game,str) or len(game.split('@'))!=2
                    or team not in game.split('@') or not isinstance(source,str)
                    or not source.startswith('https://www.nba.com/game/')):
                raise ValueError
        except (ValueError,TypeError,KeyError):
            rejected['invalid_or_future']+=1
            continue
        r['game_date']=day
        r['_complete']=(_number(r.get('minutes'),10,60)
                        and all(_number(r.get(k),0,150) for k in FIELDS))
        groups[(pid,team)].append(r)
    output=[]
    for (pid,team),history in sorted(groups.items()):
        counts=Counter(r['game_date'] for r in history)
        history=sorted(history,key=lambda r:r['game_date'])
        for i,target in enumerate(history):
            for n in COHORTS:
                if i<n:
                    continue
                prior=history[i-n:i]
                if any(counts[r['game_date']]!=1 or not r['_complete'] for r in [*prior,target]):
                    rejected[f'{n}_incomplete_or_duplicate']+=1
                    continue
                windows=(2,4,8) if n==8 else (2,4,8,12)
                samples={k:_components(prior[-k:],[1]*k) for k in windows}
                actual=_components([target],[1])
                if actual is None or any(v is None for v in samples.values()):
                    rejected[f'{n}_zero_opportunity']+=1
                    continue
                predictions={f'equal_{k}':v for k,v in samples.items()}
                # Separate opportunity/efficiency/peripherals from rotation.
                for k in windows:
                    if k>4:
                        predictions[f'minutes4_rate{k}']=dict(samples[k],minutes=samples[4]['minutes'])
                        predictions[f'minutes{k}_rate4']=dict(samples[4],minutes=samples[k]['minutes'])
                if short_long_challenge:
                    # Keep the longer production rate fixed to isolate whether
                    # recent workload adds information on the same outcomes.
                    recent_minutes = mean(row['minutes'] for row in prior[-3:])
                    long_minutes = samples[n]['minutes']
                    predictions['minutes3_long_rate'] = dict(samples[n], minutes=recent_minutes)
                    predictions['minutes3_long_blend'] = dict(
                        samples[n], minutes=(recent_minutes + long_minutes) / 2)
                if rate_challenge:
                    # Same long minutes, independent production-rate challenger.
                    # Blend final FD rates, not their interacting components.
                    long, short = samples[n], samples[4]
                    # Instead of a nonlinear product of averaged components,
                    # use blended opportunity with opportunity-weighted efficiency.
                    opportunity = (long['opportunity'] + short['opportunity']) / 2
                    efficiency = (long['opportunity']*long['efficiency'] +
                                  short['opportunity']*short['efficiency']) / (2*opportunity)
                    predictions['long_minutes_blended_rate'] = dict(
                        long, opportunity=opportunity, efficiency=efficiency,
                        peripherals=(long['peripherals']+short['peripherals'])/2)
                actual_fd=_score(actual)
                actual_rate=actual_fd/actual['minutes']
                for policy,c in predictions.items():
                    pred=_score(c)
                    rate=pred/c['minutes']
                    # Symmetric decomposition: exactly reconciles point bias.
                    minutes_effect=(c['minutes']-actual['minutes'])*(rate+actual_rate)/2
                    rate_effect=(rate-actual_rate)*(c['minutes']+actual['minutes'])/2
                    output.append(dict(cohort=n,nba_id=pid,team=team,
                        date=target['game_date'].isoformat(),source=target['source'],
                        training_dates=[r['game_date'].isoformat() for r in prior],
                        policy=policy,predicted_fd=pred,actual_fd=actual_fd,
                        fd_abs_error=abs(pred-actual_fd),fd_bias=pred-actual_fd,
                        predicted_minutes=c['minutes'],actual_minutes=actual['minutes'],
                        predicted_fppm=rate,actual_fppm=actual_rate,
                        fppm_abs_error=abs(rate-actual_rate),fppm_bias=rate-actual_rate,
                        minutes_bias=c['minutes']-actual['minutes'],
                        minutes_effect=minutes_effect,rate_effect=rate_effect,
                        minutes_abs_error=abs(c['minutes']-actual['minutes']),
                        opportunity_abs_error=abs(c['opportunity']-actual['opportunity']),
                        efficiency_abs_error=abs(c['efficiency']-actual['efficiency']),
                        peripheral_abs_error=abs(c['peripherals']-actual['peripherals'])))
    daily=[]
    by_day=defaultdict(list)
    for r in output:
        by_day[r['cohort'],r['date'],r['policy']].append(r)
    for (n,day,p),rows in sorted(by_day.items()):
        daily.append(dict(cohort=n,date=day,policy=p,players=len(rows),
                          **{k:mean(r[k] for r in rows) for k in METRICS}))
    summary=[]
    by_policy=defaultdict(list)
    for r in daily:
        by_policy[r['cohort'],r['policy']].append(r)
    for (n,p),rows in sorted(by_policy.items()):
        summary.append(dict(cohort=n,policy=p,dates=len(rows),player_games=sum(r['players'] for r in rows),
                            **{k:mean(r[k] for r in rows) for k in METRICS}))
    return dict(rows=output,daily=daily,summary=summary,rejected=dict(rejected),
                status='History-only retrospective; identical target rows within each cohort, not across cohorts',
                certified=False)
