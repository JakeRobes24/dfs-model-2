"""Evaluate the manually frozen early NBA reference; never alters scoring."""
from collections import defaultdict
from statistics import mean
from math import isfinite
import unicodedata
from nfl_forward_component_reference import stamp

# Blocks are absent from the captured provider, so this subtotal is not FD total.
WEIGHTS = {'points':1,'rebounds':1.2,'assists':1.5,'steals':3,'turnovers':-1}
STATS = set(WEIGHTS) | {'threes'}


def name_key(name):
    if not isinstance(name,str) or not name.strip():
        raise ValueError('Player name required')
    return ''.join(c for c in unicodedata.normalize('NFKD',name).casefold() if c.isalnum())


def key(r):
    game,team=r.get('game'),r.get('team')
    if not isinstance(game,str) or game.count('@')!=1 or team not in game.split('@') or len(set(game.split('@')))!=2:
        raise ValueError('Require exact oriented matchup')
    return name_key(r['player']),team,game


def valid(v,maximum=150):
    return type(v) in (int,float) and isfinite(v) and 0<=v<=maximum


def error_metrics(values):
    return dict(n=len(values),mae=mean(abs(v) for v in values),bias=mean(values)) if values else dict(n=0,mae=None,bias=None)


def compare_capture(capture, actuals):
    """Actuals need independently reviewed official ID, final status and exact tip.

    Evaluate positive played minutes separately from availability. The provider
    labelled range is nominal 80%, not assumed to be exact percentile endpoints.
    Publication-unknown house records remain exploratory. No inferred zero.
    """
    if capture.get('schema')!=1 or not isinstance(capture.get('rows'),list):
        raise ValueError('Invalid capture schema')
    reviewed=stamp(capture['reviewed_at'])
    if set(capture['sources'])!={'house','capper'}:
        raise ValueError('Expected two recorded references')
    for meta in capture['sources'].values():
        if meta.get('published_at') is not None and stamp(meta['published_at'])>reviewed:
            raise ValueError('Publication after review')
    by_key={}
    ids=set()
    for r in actuals:
        k=key(r)
        pid=r.get('official_player_id')
        if (k in by_key or not isinstance(pid,str) or not pid.strip() or
            (pid,r['game']) in ids or r.get('identity_verified') is not True or
            not isinstance(r.get('source'),str) or not r['source'].strip()):
            raise ValueError('Unique verified official outcome required')
        by_key[k]=r
        ids.add((pid,r['game']))
    seen=set()
    coverage=defaultdict(int)
    minutes=defaultdict(list)
    stats=defaultdict(list)
    ranges=[]
    partial=[]
    for r in capture['rows']:
        k=key(r)
        if k in seen:
            raise ValueError('Duplicate captured player')
        seen.add(k)
        tip=stamp(r['tip_utc'])
        if reviewed>=tip:
            raise ValueError('Review must precede scheduled tip')
        house=r['house_minutes']
        f=r['capper']
        cm,lo,hi=(f[k] for k in ('minutes','minutes_lower80','minutes_upper80'))
        if (not all(valid(v,48) for v in (house,cm,lo,hi)) or not lo<=cm<=hi
                or any(not valid(f.get(k)) for k in STATS)):
            raise ValueError('Invalid captured numerical record')
        a=by_key.get(k)
        if a is None:
            coverage['unmatched']+=1
            continue
        if stamp(a['tip_utc'])!=tip:
            raise ValueError('Tip mismatch')
        if a.get('final') is not True or stamp(a['observed_at'])<=tip:
            coverage['unverified_final']+=1
            continue
        am=a.get('minutes')
        if a.get('participation')!='played' or not valid(am,70) or am<=0:
            coverage['nonplay_or_unknown']+=1
            continue
        coverage['matched_played']+=1
        band='house_under25' if house<25 else 'house_25plus'
        for group in ('all',band):
            minutes[group].append((house-am,cm-am))
        ranges.append((lo<=am<=hi,hi-lo,(hi-lo)+10*max(lo-am,am-hi,0)))
        actual=a.get('components',{})
        for k in STATS:
            if valid(actual.get(k)):
                stats[k].append(f[k]-actual[k])
        if all(valid(actual.get(k)) for k in WEIGHTS):
            fp=sum(f[k]*w for k,w in WEIGHTS.items())
            ap=sum(actual[k]*w for k,w in WEIGHTS.items())
            if min(cm,am)>=10:
                partial.append((fp-ap,fp/cm-ap/am,house*fp/cm-ap))
    return dict(captured_players=len(seen),coverage=dict(coverage),
                minutes={g:{'house':error_metrics([r[0] for r in v]),
                            'capper':error_metrics([r[1] for r in v])} for g,v in minutes.items()},
                capper_components={k:error_metrics(v) for k,v in stats.items()},
                capper_nominal80_minutes=dict(n=len(ranges),
                    coverage=mean(r[0] for r in ranges) if ranges else None,
                    width=mean(r[1] for r in ranges) if ranges else None,
                    interval_score=mean(r[2] for r in ranges) if ranges else None),
                partial_fd_without_blocks={'capper':error_metrics([r[0] for r in partial]),
                    'capper_rate':error_metrics([r[1] for r in partial]),
                    'house_minutes_capper_rate':error_metrics([r[2] for r in partial])},
                certified=False,warning='Exploratory played-only reference; partial FD excludes blocks, not a full score.')
