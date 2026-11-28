"""Advisory, forward component comparisons for manually preserved NFL references.

No projection weights, points conversion, lineup selection or official identity
lookup. The caller must independently reconcile official final outcomes.
"""
from collections import defaultdict
from datetime import datetime
from math import isfinite
from statistics import mean
import unicodedata

PROVIDERS = ('Volt Fantasy', 'Malter Analytics')
METRICS = {'passing_yards','passing_td','interceptions','rushing_attempts',
           'rushing_yards','targets','receptions','receiving_yards','receiving_td'}
SIGNED = {'passing_yards','rushing_yards','receiving_yards'}


def stamp(s):
    if not isinstance(s,str):
        raise ValueError('Timezone-aware timestamp required')
    t = datetime.fromisoformat(s.replace('Z','+00:00'))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('Timezone-aware timestamp required')
    return t


def key(row):
    name = row.get('player')
    if not isinstance(name,str):
        raise ValueError('Player name required')
    name = ''.join(c for c in unicodedata.normalize('NFKD',name).casefold()
                   if c.isalnum())
    team, game, position = (row.get(k) for k in ('team','game','position'))
    if (not name or not isinstance(team,str) or not isinstance(game,str)
            or game.count('@')!=1 or team not in game.split('@')
            or len(set(game.split('@')))!=2 or position not in ('QB','RB','WR','TE')):
        raise ValueError('Exact normalized name, team, oriented game and position required')
    return name,team,game,position


def value(metric, x):
    return (type(x) in (int,float) and isfinite(x)
            and (metric in SIGNED or x>=0))


def check_components(fields):
    if not isinstance(fields,dict) or not set(fields)<=METRICS:
        raise ValueError('Unsupported component schema')
    if any(not value(k,v) for k,v in fields.items()):
        raise ValueError('Invalid component value')


def compare_capture(capture, actuals):
    """One preserved pregame reference, identical component/outcome support.

    A review-clock timestamp is not authenticated network capture evidence.
    Publication-unknown estimates are included as explicitly exploratory.
    Official source and stable ID verification are caller-attested, not
    inferred from names. Explicit nonplay and unknown results are excluded.
    """
    if capture.get('schema')!=1 or not isinstance(capture.get('rows'),list):
        raise ValueError('Unsupported capture schema')
    reviewed = stamp(capture['reviewed_at'])
    if set(capture['sources'])!=set(PROVIDERS):
        raise ValueError('Expected the two recorded providers')
    for provider in PROVIDERS:
        meta = capture['sources'][provider]
        pub = meta.get('published_at')
        if pub is not None and stamp(pub)>reviewed:
            raise ValueError('Publication after reference review')
    by_key, stable_ids = {}, set()
    for r in actuals:
        k=key(r)
        identity=r.get('official_player_id')
        if k in by_key:
            raise ValueError('Duplicate outcome identity')
        if (not isinstance(identity,str) or not identity.strip()
                or not isinstance(r.get('source'),str) or not r['source'].strip()
                or r.get('identity_verified') is not True):
            raise ValueError('Official outcome identity must be independently reviewed')
        token=(identity,r['game'])
        if token in stable_ids:
            raise ValueError('Duplicate official player/game')
        stable_ids.add(token)
        check_components(r.get('components',{}))
        by_key[k]=r
    seen, scores, coverage = set(), defaultdict(list), defaultdict(int)
    detail=[]
    for r in capture['rows']:
        k=key(r)
        if k in seen:
            raise ValueError('Duplicate captured player')
        seen.add(k)
        kickoff=stamp(r['kickoff_utc'])
        if reviewed>=kickoff:
            raise ValueError('Capture review must precede scheduled kickoff')
        fs=r['forecasts']
        if set(fs)!=set(PROVIDERS):
            raise ValueError('Expected paired provider rows')
        for f in fs.values():
            check_components(f)
        hit=by_key.get(k)
        if hit is None:
            coverage['unmatched_outcome']+=1
            continue
        if stamp(hit['kickoff_utc'])!=kickoff:
            raise ValueError('Kickoff mismatch')
        if hit.get('final') is not True or stamp(hit['observed_at'])<=kickoff:
            coverage['unverified_final']+=1
            continue
        if hit.get('participation')!='played':
            coverage['nonplay_or_unknown']+=1
            continue
        a=hit.get('components',{})
        common=set(fs[PROVIDERS[0]]) & set(fs[PROVIDERS[1]]) & set(a)
        if not common:
            coverage['no_common_component']+=1
            continue
        coverage['matched_played']+=1
        for metric in sorted(common):
            errors={p:fs[p][metric]-a[metric] for p in PROVIDERS}
            scores[(r['position'],metric)].append(errors)
            detail.append(dict(player_id=hit['official_player_id'],game=r['game'],
                               position=r['position'],metric=metric,actual=a[metric],
                               forecasts={p:fs[p][metric] for p in PROVIDERS}))
    result=[]
    for (position,metric),rows in sorted(scores.items()):
        result.append(dict(position=position,metric=metric,n=len(rows),
                           errors={p:dict(mae=mean(abs(r[p]) for r in rows),
                                          bias=mean(r[p] for r in rows))
                                   for p in PROVIDERS}))
    return dict(captured_players=len(seen),coverage=dict(coverage),matched_components=detail,
                comparison=result,publication_unknown=[p for p in PROVIDERS
                    if capture['sources'][p].get('published_at') is None],
                certified=False,warning='Exploratory matched statistical components only; no scoring acceptance.')
