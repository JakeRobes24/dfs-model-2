"""Availability probability evaluation with unresolved outcomes kept explicit.

Research only. Bounds describe missing-outcome uncertainty, not a statistical
confidence interval, probability estimate, or live score adjustment.
"""
from math import isfinite
from statistics import mean


def availability_bounds(rows, forecasts, *, anchor):
    """Evaluate fixed DNP probabilities on an identical pool.

    Each row has unique exact contest id, outcome (played, did_not_play,
    unknown), and all requested DNP probabilities. Unknown outcomes can
    only be either played or nonplayed. Pairwise differences use the SAME
    possible outcome for both forecasts, rather than subtracting unrelated
    marginal bounds. No imputation or assumed missingness mechanism.
    """
    fields=tuple(forecasts)
    if not fields or len(set(fields))!=len(fields) or anchor not in fields:
        raise ValueError('Unique forecast fields and anchor required')
    if any(not isinstance(f,str) or not f or f in ('id','outcome') for f in fields):
        raise ValueError('Invalid probability field')
    rows=list(rows)
    seen=set()
    known=[]
    unknown=[]
    for row in rows:
        pid=row.get('id')
        if not isinstance(pid,str) or not pid.strip() or pid in seen:
            raise ValueError('Unique exact contest IDs required')
        seen.add(pid)
        label=row.get('outcome')
        if label not in ('played','did_not_play','unknown'):
            raise ValueError('Explicit participation outcome required')
        if not all(type(row.get(f)) in (int,float) and isfinite(row[f]) and 0<=row[f]<=1 for f in fields):
            raise ValueError('Common valid probability support required')
        if label=='unknown':
            unknown.append(row)
        else:
            known.append((row,int(label=='did_not_play')))
    n=len(rows)
    dnp=sum(y for _,y in known)
    def bounds(f):
        observed=[f(r,y) for r,y in known]
        alternatives=[(f(r,0),f(r,1)) for r in unknown]
        return dict(known_mean=mean(observed) if observed else None,
                    lower=(sum(observed)+sum(min(a,b) for a,b in alternatives))/n if n else None,
                    upper=(sum(observed)+sum(max(a,b) for a,b in alternatives))/n if n else None)
    result=dict(players=n,known=len(known),unknown=len(unknown),confirmed_dnp=dnp,
                observed_dnp_rate=dnp/len(known) if known else None,
                possible_dnp_rate=(dnp/n,(dnp+len(unknown))/n) if n else (None,None),
                forecasts={},comparisons={})
    for f in fields:
        result['forecasts'][f]=dict(predicted_dnp_rate=mean(r[f] for r in rows) if n else None,
                                    **bounds(lambda r,y:(r[f]-y)**2))
        if f==anchor:
            continue
        comparison=bounds(lambda r,y:(r[f]-y)**2-(r[anchor]-y)**2)
        lo,hi=comparison['lower'],comparison['upper']
        comparison['direction']=('no evidence' if lo is None else
                                  'better for every completion' if hi<0 else
                                  'worse for every completion' if lo>0 else
                                  'direction unresolved')
        result['comparisons'][f]=comparison
    return result
