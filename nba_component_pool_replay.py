"""Chronological NBA component pooling comparison; research only."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from math import isfinite

from nba_component_history import FIELDS, _number
from opportunity_evidence import FD_WEIGHTS

CHANNELS=('net','reb','ast','stocks')
PRIOR_MINUTES=100
PRIOR_OPPORTUNITIES=40

def totals(rows):
    return dict(minutes=sum(r['minutes'] for r in rows),
                opp=sum(r['fieldGoalsAttempted']+.44*r['freeThrowsAttempted']+r['turnovers'] for r in rows),
                net=sum(r['points']-r['turnovers'] for r in rows),
                reb=sum(1.2*r['reboundsTotal'] for r in rows),
                ast=sum(1.5*r['assists'] for r in rows),
                stocks=sum(3*(r['steals']+r['blocks']) for r in rows))

def component_pool_forecast(prior, cohort):
    """Four earlier complete personal games; strictly earlier pooled totals.
    
    Net scoring efficiency uses a fixed 40 opportunity prior while holding
    personal opportunity frequency fixed. Other channels use 100 minutes.
    This does not forecast official usage or tracked rebound chances.
    """
    if len(prior)!=4:
        raise ValueError('Four complete prior games required')
    a=totals(prior)
    if min(a['minutes'],a['opp'],cohort['opp'],cohort['minutes'])<=0:
        return None
    m=a['minutes']/4
    base={k:a[k]/4 for k in CHANNELS}
    alt={k:m*(a[k]+PRIOR_MINUTES*cohort[k]/cohort['minutes'])/(a['minutes']+PRIOR_MINUTES)
         for k in ('reb','ast','stocks')}
    alt['net']=a['opp']/4*(a['net']+PRIOR_OPPORTUNITIES*cohort['net']/cohort['opp'])/(a['opp']+PRIOR_OPPORTUNITIES)
    return base,alt,m

def component_pool_replay(records,cutoff):
    """Compare channel-only and joint policies on exact common played support.

    No target-date outcomes enter forecasts. Missing and duplicate prior rows
    remain in chronology and veto the window. Not a full contest projection.
    """
    if type(cutoff) is not date:
        raise ValueError('Exact cutoff date required')
    groups=defaultdict(list)
    daily=defaultdict(list)
    rejected=Counter()
    for raw in records:
        try:
            day=date.fromisoformat(str(raw['game_date'])[:10])
            pid=str(raw['nba_id'])
            team=raw['team']
            game=raw['game']
            if (not pid.isdigit() or not isinstance(team,str) or not team
                    or not isinstance(game,str) or len(game.split('@'))!=2
                    or len(set(game.split('@')))!=2 or team not in game.split('@')
                    or not raw['source'].startswith('https://www.nba.com/game/')):
                raise ValueError('Identity or source')
        except (KeyError,TypeError,ValueError,AttributeError):
            rejected['identity_or_source']+=1
            continue
        if day>=cutoff:
            rejected['on_or_after_cutoff']+=1
            continue
        complete=(_number(raw.get('minutes'),10,60)
                  and all(_number(raw.get(k),0,150) for k in FIELDS))
        groups[pid,team].append(dict(raw,day=day,complete=complete))
    for hist in groups.values():
        count=Counter(r['day'] for r in hist)
        for r in hist:
            if r['complete'] and count[r['day']]==1:
                daily[r['day']].append(r)
    earlier={}
    cumulative=totals([])
    for day,rs in sorted(daily.items()):
        earlier[day]=cumulative.copy()
        for k,v in totals(rs).items():
            cumulative[k]+=v
    output=[]
    for (pid,team),hist in sorted(groups.items()):
        hist.sort(key=lambda r:r['day'])
        count=Counter(r['day'] for r in hist)
        for i in range(4,len(hist)):
            prior,target=hist[i-4:i],hist[i]
            if any(count[r['day']]!=1 or not r['complete'] for r in [*prior,target]):
                rejected['incomplete_or_duplicate']+=1
                continue
            if target['day']-prior[0]['day']>timedelta(days=30):
                rejected['old_window']+=1
                continue
            predicted=component_pool_forecast(prior,earlier[target['day']])
            if predicted is None:
                rejected['insufficient_opportunities']+=1
                continue
            base,alt,m=predicted
            actual=totals([target])
            row=dict(date=target['day'].isoformat(),nba_id=pid,team=team,
                     history_end=prior[-1]['day'].isoformat(),minutes=m,
                     actual_fd=sum(actual[k] for k in CHANNELS),base_fd=sum(base.values()))
            for k in CHANNELS:
                row.update({f'actual_{k}':actual[k],f'base_{k}':base[k],f'pool_{k}':alt[k],
                            f'only_{k}_fd':row['base_fd']-base[k]+alt[k]})
            row['all_pool_fd']=sum(alt.values())
            output.append(row)
    return output,dict(rejected)
