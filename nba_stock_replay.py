"""Historical-only NBA defensive production comparison; never modifies live scoring."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from math import isfinite
from statistics import mean

FD_WEIGHTS={'points':1,'reboundsTotal':1.2,'assists':1.5,'steals':3,'blocks':3,'turnovers':-1}
SHRINK_MINUTES=100


def stock_replay(records, cutoff, *, window=4):
    """Hold recent four-game minutes and non-stock production fixed.

    Compare observed personal stocks/min with a fixed 100-minute prior at the
    pooled earlier-date rate, excluding ambiguous/short observations. Eight
    game mode isolates longer personal history and combined sensitivity.
    No target-date values enter forecasts. Played-only historical comparison.
    """
    if type(cutoff) is not date or window not in (4,8):
        raise ValueError('Exact cutoff date and four/eight-game window required')
    groups=defaultdict(list)
    daily=defaultdict(lambda:[0.,0.])
    rejected=Counter()
    for raw in records:
        try:
            day=date.fromisoformat(str(raw['game_date'])[:10])
            pid=str(raw['nba_id'])
            team=raw['team']
            game=raw['game']
            if (not pid.isdigit() or not isinstance(team,str) or not team or
                not isinstance(game,str) or len(game.split('@'))!=2 or
                len(set(game.split('@')))!=2 or team not in game.split('@') or
                not raw['source'].startswith('https://www.nba.com/game/')):
                raise ValueError('Identity or source')
        except (KeyError,TypeError,ValueError,AttributeError):
            rejected['identity_or_source']+=1
            continue
        if day>=cutoff:
            rejected['on_or_after_cutoff']+=1
            continue
        m=raw.get('minutes')
        complete=(type(m) in (int,float) and isfinite(m) and 10<=m<=60 and
                  all(type(raw.get(k)) in (int,float) and 0<=raw[k]<=150
                      for k in FD_WEIGHTS))
        groups[pid,team].append(dict(raw,day=day,complete=complete))
    stock=lambda rs:sum(3*(r['steals']+r['blocks']) for r in rs)
    minutes=lambda rs:sum(r['minutes'] for r in rs)
    score=lambda r:sum(r[k]*w for k,w in FD_WEIGHTS.items())
    for hist in groups.values():
        count=Counter(r['day'] for r in hist)
        for r in hist:
            if r['complete'] and count[r['day']]==1:
                daily[r['day']][0]+=stock([r])
                daily[r['day']][1]+=r['minutes']
    output=[]
    for (pid,team),hist in sorted(groups.items()):
        hist.sort(key=lambda r:r['day'])
        count=Counter(r['day'] for r in hist)
        for i in range(window,len(hist)):
            prior,target=hist[i-window:i],hist[i]
            if any(count[r['day']]!=1 or not r['complete'] for r in [*prior,target]):
                rejected['incomplete_or_duplicate']+=1
                continue
            if target['day']-prior[0]['day']>timedelta(days=30):
                rejected['old_window']+=1
                continue
            totals=[v for day,v in daily.items() if day<target['day']]
            total_minutes=sum(v[1] for v in totals)
            if total_minutes<=0:
                rejected['missing_earlier_cohort']+=1
                continue
            cohort=sum(v[0] for v in totals)/total_minutes
            recent=prior[-4:]
            m=minutes(recent)/4
            personal=stock(recent)/minutes(recent)
            non=mean(score(r)-stock([r]) for r in recent)
            policies={'four_game':personal,
                      'pooled_100min':(stock(recent)+SHRINK_MINUTES*cohort)/(minutes(recent)+SHRINK_MINUTES)}
            if window==8:
                longer=stock(prior)/minutes(prior)
                policies.update(eight_game_stocks=longer,half_long_stocks=(personal+longer)/2,
                    long_pooled_100min=(stock(prior)+SHRINK_MINUTES*cohort)/(minutes(prior)+SHRINK_MINUTES))
            row=dict(date=target['day'].isoformat(),nba_id=pid,team=team,
                     history_end=prior[-1]['day'].isoformat(),forecast_minutes=m,
                     actual_minutes=target['minutes'],actual_fd=score(target),
                     actual_stocks=stock([target]),nonstock_forecast=non,
                     base_stock_share=m*personal/(non+m*personal) if non+m*personal>0 else None)
            for name,rate in policies.items():
                row[name+'_rate']=rate
                row[name+'_stock']=m*rate
                row[name+'_fd']=non+m*rate
            output.append(row)
    return output,dict(rejected)
