"""Read-only chronological interval and order diagnostics on archived NBA rosters."""
from statistics import mean
from math import isfinite
from datetime import datetime
import json,zipfile,hashlib,argparse
from pathlib import Path

WIDTHS=(1.,1.25,1.5,2.)
ORDER_WEIGHTS=(0.,.5,1.)
POLICIES=('point_residual','paired_minutes_rate')

def interval_metrics(rows,factor):
    if factor<1 or not isfinite(factor):raise ValueError('Invalid width factor')
    out=[]
    for r in rows:
        lo,m,hi,y=(r[k] for k in ('fd_p10','fd_p50','fd_p90','actual'))
        if not all(isfinite(v) for v in (lo,m,hi,y)) or not lo<=m<=hi:raise ValueError('Invalid interval')
        a,b=m+factor*(lo-m),m+factor*(hi-m)
        out.append((a<=y<=b,b-a,b-a+10*max(a-y,0)+10*max(y-b,0),y<a,y>b))
    return dict(n=len(out),**{k:mean(x[i] for x in out) for i,k in enumerate(('coverage','width','interval_score','below','above'))})

def order_metrics(rows,weight):
    if not 0<=weight<=1:raise ValueError('Invalid probability weight')
    e=[];p0=[];p1=[]
    for r in rows:
        p,t,a,g=(r[k] for k in ('lineup_ahead_share','tie_share','alternative_ahead_share','actual_gap'))
        if not all(isfinite(v) for v in (p,t,a,g)) or min(p,t,a)<0 or abs(p+t+a-1)>1e-8:raise ValueError('Invalid pair probabilities')
        if g==0:continue
        y=float(g>0);raw=p+t/2
        e.append((.5+weight*(raw-.5)-y)**2)
        p0.append((.5-y)**2)
        # Hard point ranking is a descriptive comparator, not a calibrated probability.
        q=1. if r['reviewed_gap']>0 else 0. if r['reviewed_gap']<0 else .5
        p1.append((q-y)**2)
    return dict(n=len(e),brier=mean(e) if e else None,neutral=mean(p0) if p0 else None,hard_points=mean(p1) if p1 else None)

def replay(slates):
    dated=[]; seen=set()
    for s in sorted(slates,key=lambda x:x['date']):
        day=s['date']; meta=s['metadata']
        if day in seen:raise ValueError('Duplicate slate date')
        seen.add(day)
        if not meta.get('captured_at') or not meta.get('first_tip'):continue
        capture=datetime.fromisoformat(meta['captured_at']);tip=datetime.fromisoformat(meta['first_tip'])
        if capture.tzinfo is None or tip.tzinfo is None or capture>=tip:raise ValueError('Invalid capture chronology')
        if s['training']['training_latest']>=day:raise ValueError('Training leakage')
        d=dict(date=day,policies={})
        for p in POLICIES:
            rs=[r for r in s['lineups'] if r['policy']==p]; ps=[r for r in s['pairs'] if r['policy']==p]
            if len({r['lineup'] for r in rs})!=len(rs) or len({(r['lineup'],r['alternative']) for r in ps})!=len(ps):raise ValueError('Duplicate candidate or pair')
            roster={r['lineup']:(r['actual'],r['reviewed']) for r in rs}
            pairs={(r['lineup'],r['alternative']):(r['actual_gap'],r['reviewed_gap']) for r in ps}
            if p==POLICIES[0]:common=(roster,pairs)
            elif common!=(roster,pairs):raise ValueError('Mismatched policy support')
            d['policies'][p]=dict(widths={f:interval_metrics(rs,f) for f in WIDTHS},order={w:order_metrics(ps,w) for w in ORDER_WEIGHTS})
        dated.append(d)
    for i,d in enumerate(dated):
        if i==0:continue
        for p in POLICIES:
            prior=[x['policies'][p] for x in dated[:i]]
            f=min(WIDTHS,key=lambda f:(mean(x['widths'][f]['interval_score'] for x in prior),f))
            w=min(ORDER_WEIGHTS,key=lambda w:(mean(x['order'][w]['brier'] for x in prior if x['order'][w]['n']),w)) if any(x['order'][0.]['n'] for x in prior) else None
            d['policies'][p].update(selected_width=f,selected_order=w,training_dates=[x['date'] for x in dated[:i]])
    return dated

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path);args=parser.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        manifest=json.load(z.open('manifest.json'))
        for n,record in manifest['outputs'].items():
            b=z.read(n)
            if hashlib.sha256(b).hexdigest()!=record['sha256'] or len(b)!=record['bytes']:raise ValueError('Output digest mismatch')
        print(json.dumps(replay(json.load(z.open('multi-slate.json'))['slates']),indent=2))
