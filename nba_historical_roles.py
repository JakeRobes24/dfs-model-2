"""Research-only cross-check of historical starter flags against final box scores.

Never infer a starting role from minutes or player order. A role is accepted
only from an explicit flag and a complete five-starter team box, matched to the
original official NBA box by exact game and team/player identity.
"""
from collections import Counter
from math import isfinite
import re
from slate_import import player_key, team_code

def flag(value):
    if type(value) is bool:
        return value
    if type(value) is int and value in (0,1):
        return bool(value)
    if isinstance(value,str) and value in ('0','1'):
        return value=='1'
    return None

def minutes(value):
    if isinstance(value,str):
        iso=re.fullmatch(r'PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?',value)
        if iso and (iso[1] or iso[2]):
            value=float(iso[1] or 0)+float(iso[2] or 0)/60
        elif re.fullmatch(r'\d{1,2}:\d{2}',value):
            m,s=map(int,value.split(':'))
            if s>=60:
                return None
            value=m+s/60
        elif re.fullmatch(r'\d+(?:\.\d+)?',value):
            value=float(value)
    if type(value) not in (int,float) or not isfinite(value) or not 0<=value<=60:
        return None
    return float(value)

def official_roles(game, game_id, away, home):
    """NBA liveData final box only; exact game ID and ordered teams."""
    if str(game.get('gameId'))!=game_id or game.get('gameStatus')!=3:
        raise ValueError('NBA role box is not the exact final game')
    out={}
    for side,team in [('awayTeam',away),('homeTeam',home)]:
        club=game.get(side) or {}
        if team_code(club.get('teamTricode',''))!=team:
            raise ValueError('NBA role box team mismatch')
        entries=[]
        for p in club.get('players',[]):
            m=minutes((p.get('statistics') or {}).get('minutes'))
            if m is None or m<=0:
                continue
            entries.append((str(p.get('personId') or ''),m,flag(p.get('starter'))))
        if (any(not k.isdigit() or f is None for k,m,f in entries)
                or len({k for k,m,f in entries})!=len(entries)
                or sum(f is True for k,m,f in entries)!=5):
            raise ValueError('Incomplete or conflicting NBA starter flags')
        out[team]={k:(m,f) for k,m,f in entries}
    return out

def espn_roles(data, event_id, away, home):
    """Secondary ESPN final box. Names are matched only with exact team and minutes."""
    header=data.get('header') or {}
    if str(header.get('id'))!=event_id:
        raise ValueError('ESPN event identity mismatch')
    comps=header.get('competitions') or []
    if len(comps)!=1 or (comps[0].get('status') or {}).get('type',{}).get('completed') is not True:
        raise ValueError('ESPN event not final')
    teams={c.get('homeAway'):team_code((c.get('team') or {}).get('abbreviation',''))
           for c in comps[0].get('competitors',[])}
    if teams!={'away':away,'home':home}:
        raise ValueError('ESPN role box team mismatch')
    out={}
    for side in (data.get('boxscore') or {}).get('players',[]):
        team=team_code((side.get('team') or {}).get('abbreviation',''))
        if team not in {away,home} or team in out:
            raise ValueError('ESPN role box duplicate/unexpected team')
        entries=[]
        for group in side.get('statistics',[]):
            labels=group.get('labels',[])
            if labels.count('MIN')!=1:
                continue
            for p in group.get('athletes',[]):
                stats=p.get('stats',[])
                if p.get('didNotPlay') is True or len(stats)!=len(labels):
                    continue
                m=minutes(stats[labels.index('MIN')])
                if m is None or m<=0:
                    continue
                name=player_key((p.get('athlete') or {}).get('displayName',''))
                entries.append((name,m,flag(p.get('starter'))))
        if (any(not k or f is None for k,m,f in entries)
                or len({k for k,m,f in entries})!=len(entries)
                or sum(f is True for k,m,f in entries)!=5):
            raise ValueError('Incomplete or conflicting ESPN starter flags')
        out[team]={k:(m,f) for k,m,f in entries}
    if set(out)!={away,home}:
        raise ValueError('Incomplete ESPN team box')
    return out

def enrich_roles(rows, roles, *, source, by_name=False):
    """Attach research flags only after complete per-team identity/minutes agreement.

    No partial team assignment, no false bench label for a missing flag.
    Existing explicit flags are never overwritten when there is a conflict.
    """
    result=[dict(r) for r in rows]
    for team,lookup in roles.items():
        group=[r for r in result if r['team']==team]
        keys=[player_key(r['player']) if by_name else str(r['nba_id']) for r in group]
        if (len(keys)!=len(set(keys)) or set(keys)!=set(lookup)
                or any(abs(float(r['minutes'])-lookup[k][0])>(1.01 if by_name else .02)
                       for k,r in zip(keys,group))
                or any(type(r.get('started')) is bool and r['started']!=lookup[k][1]
                       for k,r in zip(keys,group))):
            continue
        for k,r in zip(keys,group):
            r['started']=lookup[k][1]
            r['historical_role_source']=source
    return result


def recover_espn_roles(rows, *, cutoff_day, load_json, max_games=48, max_workers=4):
    """Bounded research-only recovery from exact final ESPN games.

    Dates and games come exclusively from existing NBA box observations.
    Schedule mapping is exact by Eastern game date and ordered teams.
    Return untouched rows for unavailable/ambiguous sources, with counts.
    """
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date,datetime
    from zoneinfo import ZoneInfo
    if not 1<=max_games<=150 or not 1<=max_workers<=8:
        raise ValueError('Invalid role research request bounds')
    grouped=defaultdict(list)
    for r in rows:
        try:
            day=r['game_date'] if type(r['game_date']) is date else date.fromisoformat(r['game_date'])
            away,home=r['game'].split('@')
            if day>=cutoff_day or away==home or r['team'] not in {away,home}:
                raise ValueError
            grouped[(day,away,home)].append(dict(r))
        except (ValueError,TypeError,KeyError):
            raise ValueError('Role recovery requires earlier dated exact NBA boxes')
    pending=[k for k,g in grouped.items() if any(type(r.get('started')) is not bool for r in g)]
    chosen=sorted(pending,reverse=True)[:max_games]
    def schedule(day):
        url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={day:%Y%m%d}'
        found=defaultdict(list)
        try:
            for event in load_json(url).get('events',[]):
                comps=event.get('competitions',[])
                if len(comps)!=1 or comps[0].get('status',{}).get('type',{}).get('completed') is not True:
                    continue
                stamp=datetime.fromisoformat(str(event.get('date','')).replace('Z','+00:00'))
                if stamp.tzinfo is None or stamp.astimezone(ZoneInfo('America/New_York')).date()!=day:
                    continue
                teams={p.get('homeAway'):team_code(p.get('team',{}).get('abbreviation',''))
                       for p in comps[0].get('competitors',[])}
                eid=str(event.get('id',''))
                if set(teams)=={'away','home'} and eid.isdigit():
                    found[(teams['away'],teams['home'])].append(eid)
            return day,found,'ok'
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            return day,{},'unavailable'
    def retrieve(key):
        day,away,home=key
        original=grouped[key]
        ids=schedules.get(day,{}).get((away,home),[])
        if len(ids)!=1:
            return key,original,'unmatched or ambiguous event'
        url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={ids[0]}'
        try:
            roles=espn_roles(load_json(url),ids[0],away,home)
            result=enrich_roles(original,roles,source=url,by_name=True)
            return key,result,('complete' if all(type(r.get('started')) is bool for r in result)
                               else 'partial or mismatch')
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            return key,original,'source unavailable or invalid'
    statuses=Counter()
    with ThreadPoolExecutor(max_workers=max_workers) as workers:
        schedules={}
        for day,mapping,status in workers.map(schedule,sorted({k[0] for k in chosen})):
            schedules[day]=mapping
            statuses['schedule '+status]+=1
        # Probe a small batch; avoid dozens of calls if the source is blocked.
        probe=list(workers.map(retrieve,chosen[:3]))
        results=probe
        if any(s in {'complete','partial or mismatch'} for _,_,s in probe):
            results+=list(workers.map(retrieve,chosen[3:]))
        for key,result,status in results:
            grouped[key]=result
            statuses[status]+=1
        statuses['not attempted']=len(pending)-len(results)
    enriched=[r for group in grouped.values() for r in group]
    report=dict(total=len(enriched),known=sum(type(r.get('started')) is bool for r in enriched),
                pending_games=len(pending),attempted_games=len(results),statuses=dict(statuses))
    return enriched,report
