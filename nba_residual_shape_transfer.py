"""Transfer strictly earlier point residual shapes to unchanged reviewed means.

Research only: conditional on playing, not a calibrated live simulation.
"""
from collections import defaultdict
from datetime import date
import math
import numpy as np

from nba_short_window_distribution import score

POLICIES=('raw_pool','sqrt_minutes_pool','minute_band_pool')


def _band(m):
    return 0 if m<20 else 1 if m<30 else 2


def transfer_shapes(history, reviewed, *, cutoff, minimum_rows=100, minimum_dates=3):
    """Earlier history-only residuals and already reconciled reviewed forecasts.

    Each historical row provides date, stable player id, forecast minutes,
    forecast FD and actual FD. Each reviewed row provides date, exact contest
    id, reviewed minutes, reviewed FD and verified played actual FD.
    No target outcomes contribute to the empirical residual pool. The caller
    remains responsible for history provenance and actual outcome matching.
    """
    if (type(cutoff) is not date or type(minimum_rows) is not int or minimum_rows<1
            or type(minimum_dates) is not int or minimum_dates<1):
        raise ValueError('Exact cutoff and positive minimums required')

    def validated(rows, earlier):
        seen=set()
        for row in rows:
            d=date.fromisoformat(row['date'])
            if (earlier and d>=cutoff) or (not earlier and d<cutoff):
                raise ValueError('History must strictly precede the evaluation cutoff')
            pid=row['id']
            if not isinstance(pid,str) or not pid.strip() or (d,pid) in seen:
                raise ValueError('Unique player identity per date required')
            seen.add((d,pid))
            m,p,y=(row[k] for k in ('minutes','center','actual'))
            if (not all(type(v) in (float,int) and math.isfinite(v) for v in (m,p,y))
                or not 0<m<=60 or (not earlier and not (10<=m<=48 and 0<p<=150 and p/m<=5))):
                raise ValueError('Finite matched supported points and minutes required')
            yield d,row

    prior=list(validated(history,True))
    if len(prior)<minimum_rows or len({d for d,_ in prior})<minimum_dates:
        raise ValueError('Insufficient earlier residuals')
    q=(np.arange(128)+.5)/128
    def centered(values):
        a=np.quantile(values,q)
        return a-a.mean()
    raw=centered([r['actual']-r['center'] for _,r in prior])
    scaled=centered([(r['actual']-r['center'])/math.sqrt(r['minutes']) for _,r in prior])
    groups=defaultdict(list)
    for d,r in prior:
        groups[_band(r['minutes'])].append((d,r['actual']-r['center']))
    bands={b:centered([e for _,e in rows]) for b,rows in groups.items()
           if len(rows)>=minimum_rows and len({d for d,_ in rows})>=minimum_dates}
    out=[]
    for _,r in validated(reviewed,False):
        m,p,y=(r[k] for k in ('minutes','center','actual'))
        b=_band(m)
        shapes=(raw,scaled*math.sqrt(m),bands.get(b,raw))
        for policy,shape in zip(POLICIES,shapes):
            out.append(dict(date=r['date'],id=r['id'],policy=policy,minutes=m,
                center=p,actual=y,earlier_rows=len(prior),earlier_dates=len({d for d,_ in prior}),
                band_supported=b in bands,**score(p+shape,y)))
    return out
