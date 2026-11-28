"""Read-only Friday preview triage using earlier official player observations.

Compare providers with actual historical workload and production. No contest
eligibility, current starter status, future injury or score inferred.
"""
from collections import Counter,defaultdict
from statistics import mean
from nba_component_history import FIELDS,_day,_number,_components
from nba_distribution_review import bounded,timestamp
from slate_import import player_key,matchup_key,team_code

def review_preview(preview,history,injuries=()):
    slate=_day(preview['slate_date'])
    capture=timestamp(preview['observed_at'])
    if capture is None or capture.tz_convert('America/New_York').date()>=slate:
        raise ValueError('Require a prior-day numerical preview')
    by_name=defaultdict(list)
    for r in history:
        try:
            d=_day(r['game_date'])
            pid=str(r['nba_id'])
            team=team_code(r['team'])
            name=player_key(r['player'])
            if (d>=slate or d>capture.tz_convert('America/New_York').date()
                or not pid.isdigit() or not name or not team
                or not isinstance(r['source'],str) or not r['source'].startswith('https://www.nba.com/game/')
                or team not in r['game'].split('@')):
                continue
            by_name[name].append(dict(r,game_date=d,team=team,nba_id=pid))
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
    provider_rows=defaultdict(dict)
    for provider,rows in preview['forecasts'].items():
        if provider not in {'NBA House','PropSims'}:
            raise ValueError('Unexpected provider')
        for r in rows:
            k=(player_key(r['player']),team_code(r['team']),matchup_key(r['game']))
            if provider in provider_rows[k]:
                raise ValueError('Ambiguous preview identity')
            provider_rows[k][provider]=r
    status=defaultdict(set)
    for r in injuries:
        stamp=timestamp(r.get('observed_at'))
        if r.get('official') is True and stamp is not None and stamp<=capture:
            status[(player_key(r['player']),team_code(r['team']),matchup_key(r['game']))].add(str(r['status']))
    result=[]
    for (name,team,game),providers in sorted(provider_rows.items()):
        first=next(iter(providers.values()))
        out=dict(player=first['player'],team=team,game=first['game'],
            house_minutes=bounded(providers.get('NBA House',{}).get('minutes'),0,48),
            propsims_minutes=bounded(providers.get('PropSims',{}).get('minutes'),0,48),
            propsims_fd=bounded(providers.get('PropSims',{}).get('fd_points'),0,150),
            official_status=' / '.join(sorted(status.get((name,team,game),()))) or 'No matched report row; unknown',
            history_status='No unambiguous same-team history',last3_minutes=None,last8_minutes=None,
            last8_fppm=None,last_role='unknown',history_games=0,latest_game=None)
        matches=by_name.get(name,[])
        # Unique league-wide historical name/ID; reject conflicting identities,
        # and do not use pre-trade history as current-team evidence.
        if len({r['nba_id'] for r in matches})==1:
            logs=sorted(matches,key=lambda r:r['game_date'])
            if logs and logs[-1]['team']==team:
                # A returning player may have earlier stints; use only the
                # uninterrupted latest same-team sequence.
                current=[]
                for r in reversed(logs):
                    if r['team']!=team:
                        break
                    current.append(r)
                current.reverse()
                dates=Counter(r['game_date'] for r in current)
                out['history_games']=len(current)
                out['latest_game']=current[-1]['game_date'].isoformat()
                role=current[-1].get('started')
                out['last_role']='starter' if role is True else 'bench' if role is False else 'unknown'
                out['history_status']='Same-team history; last role is not current confirmation'
                for n in (3,8):
                    sample=current[-n:]
                    if len(sample)==n and all(dates[r['game_date']]==1 and _number(r.get('minutes'),0.01,60) for r in sample):
                        out[f'last{n}_minutes']=mean(r['minutes'] for r in sample)
                        if n==8 and all(_number(r['minutes'],10,60) and all(_number(r.get(k),0,150) for k in FIELDS) for r in sample):
                            c=_components(sample,[1]*8)
                            if c:
                                out['last8_fppm']=c['opportunity']*c['efficiency']+c['peripherals']
        a,b=out['house_minutes'],out['propsims_minutes']
        h=out['last8_minutes']
        out['provider_gap']=None if a is None or b is None else b-a
        out['house_vs_history']=None if a is None or h is None else a-h
        out['propsims_vs_history']=None if b is None or h is None else b-h
        reasons=[]
        if out['provider_gap'] is not None and abs(out['provider_gap'])>=5:
            reasons.append('Provider minutes disagreement >=5')
        if any(v is not None and abs(v)>=5 for v in (out['house_vs_history'],out['propsims_vs_history'])):
            reasons.append('Historical workload discrepancy >=5')
        if out['official_status']!='No matched report row; unknown':
            reasons.append('Official report status requires review')
        if out['history_games']==0:
            reasons.append('No verified same-team history')
        out['review_reasons']=reasons
        result.append(out)
    return result
