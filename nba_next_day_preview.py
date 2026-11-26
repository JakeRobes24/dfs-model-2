"""Read-only next-day preview; never passed to the live scoring pipeline."""
from collections import Counter,defaultdict
from datetime import timedelta
import pandas as pd
from slate_import import player_key,matchup_key,team_code
from slate_research import (ET, PROPSIMS, NBA_HOUSE, _parse_propsims_board,
                            fetch_paired_provider, nba_house_minutes, public_source_failure)
from nba_distribution_review import bounded,timestamp

def preview_next_day(slate,as_of,schedule,*,propsims_loader=None,house_loader=None):
    """Require exact official future matchups. No contest IDs/salaries inferred."""
    stamp=timestamp(as_of)
    if stamp is None or slate!=stamp.tz_convert(ET).date()+timedelta(days=1):
        raise ValueError('Preview requires next Eastern calendar day')
    games={}
    teams=set()
    for g in schedule:
        away,home=(team_code(g[k]['teamTricode']) for k in ('awayTeam','homeTeam'))
        tip=timestamp(g.get('gameTimeUtc'))
        key=matchup_key(f'{away}@{home}')
        if (not away or not home or away==home or key in games or away in teams or home in teams
                or tip is None or tip<=stamp or tip.tz_convert(ET).date()!=slate):
            raise ValueError('Invalid or ambiguous next-day official schedule')
        games[key]=(away,home)
        teams.update((away,home))
    if not games:
        raise ValueError('No verified next-day official games')
    rows={}
    statuses={}
    for name in ('NBA House','PropSims'):
        try:
            if name=='NBA House':
                (notes,_),status=(house_loader or nba_house_minutes)(slate,as_of)
                estimates=notes
            else:
                raw=(propsims_loader or (lambda:fetch_paired_provider(PROPSIMS)))()
                (_,estimates),status=_parse_propsims_board(raw,slate,as_of,next_day_preview=True)
            statuses[name]=status
        except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError) as exc:
            estimates=[]
            statuses[name]=public_source_failure(exc)
        by_id=defaultdict(list)
        for e in estimates:
            key=matchup_key(e.get('game',''))
            team=team_code(e.get('team',''))
            player=player_key(e.get('player',''))
            if key not in games or team not in games[key] or not player:
                continue
            minutes=bounded(e.get('minutes') if name=='NBA House' else e.get('paired_minutes'),0,48)
            points=bounded(e.get('points'),0,150) if name=='PropSims' else None
            if minutes is None or (name=='PropSims' and points is None):
                continue
            by_id[(team,key,player)].append(dict(player=e['player'],team=team,game='@'.join(games[key]),
                minutes=minutes,fd_points=points,source=NBA_HOUSE if name=='NBA House' else PROPSIMS,
                published_at=e['observed_at'] if name=='PropSims' else None,
                observed_at=stamp.isoformat(),scoring_accepted=False))
        rows[name]={k:v[0] for k,v in by_id.items() if len(v)==1}
    overlap=[]
    for k in sorted(set(rows['NBA House'])&set(rows['PropSims'])):
        a,b=rows['NBA House'][k],rows['PropSims'][k]
        overlap.append(dict(player=a['player'],team=a['team'],game=a['game'],
            house_minutes=a['minutes'],propsims_minutes=b['minutes'],propsims_fd=b['fd_points'],
            minute_gap=round(b['minutes']-a['minutes'],2)))
    return dict(slate_date=slate.isoformat(),observed_at=stamp.isoformat(),
        games=len(games),status=statuses,coverage={p:dict(players=len(v),
            games=len({r['game'] for r in v.values()}),teams=len({r['team'] for r in v.values()}))
            for p,v in rows.items()},
        forecasts={p:list(v.values()) for p,v in rows.items()},overlap=overlap,
        warning='Next-day advisory only; not contest-matched, not independent scoring consensus, refresh on slate day.')
