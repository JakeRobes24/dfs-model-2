"""DFS Model 2.0: auditable minutes consensus, confidence and legal FanDuel optimizer."""
import re
import unicodedata
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix, vstack

SLOTS = ['PG','SG','SF','PF','C','G/F','F/C','UTIL','UTIL']

def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode().lower())

def consensus(base, evidence=None, historical=None, min_sources=2):
    """Source columns: player,source,minutes,observed_at,independent_group; historical: player,season_mpg,last5_mpg,last10_mpg.
    Sources in same independent_group are counted once to avoid syndicated false consensus.
    Missing historical/source inputs are NOT fabricated. DAILY-only rows remain provisional.
    """
    d=base.copy();d['key']=d.fanduel_name.map(norm)
    e=pd.DataFrame(columns=['player','source','minutes','independent_group']) if evidence is None else evidence.copy()
    if len(e):
        e['key']=e.player.map(norm);e['minutes']=pd.to_numeric(e.minutes,errors='coerce')
        e=e[e.minutes.between(0,48)].copy()
        if 'independent_group' not in e:e['independent_group']=e.source
        e['independent_group']=e['independent_group'].fillna(e.source)
        if 'observed_at' in e:
            e=e.sort_values('observed_at').drop_duplicates(['key','independent_group'],keep='last')
        else:e=e.drop_duplicates(['key','independent_group'],keep='last')
    h=pd.DataFrame(columns=['key','season_mpg','last5_mpg','last10_mpg']) if historical is None else historical.copy()
    if len(h):h['key']=h.player.map(norm);h=h.drop_duplicates('key',keep='last')
    h=h.drop(columns=['player'],errors='ignore')
    d=d.merge(h,on='key',how='left')
    for col in ['season_mpg','last5_mpg','last10_mpg']:
        if col not in d:d[col]=np.nan
        d[col]=pd.to_numeric(d[col],errors='coerce').where(lambda x:x.between(0,48))
    groups={k:g for k,g in e.groupby('key')} if len(e) else {}
    rows=[]
    for _,r in d.iterrows():
        g=groups.get(r.key);vals=g.minutes.to_numpy(dtype=float) if g is not None else np.array([])
        count=len(vals);spread=float(np.ptp(vals)) if count else np.nan
        historical_pairs=[(r[c],w) for c,w in [('last5_mpg',3),('last10_mpg',2),('season_mpg',1)] if pd.notna(r[c])]
        history=float(np.average([v for v,w in historical_pairs],weights=[w for v,w in historical_pairs])) if historical_pairs else np.nan
        # Recent evidence gets weight; agreement is based on independent groups and absolute range.
        agree=count>=min_sources and spread<=4
        if agree:
            estimate=float(np.median(vals));method='independent_source_consensus';confidence='high' if (pd.notna(history) and abs(estimate-history)<=5) else 'medium'
        elif count and pd.notna(history):
            estimate=float(.65*np.median(vals)+.35*history);method='source_plus_history_disagreement' if spread>4 else 'source_plus_history';confidence='medium' if spread<=6 else 'low'
        elif count:
            estimate=float(np.median(vals));method='single_source_or_disagreement';confidence='low'
        elif pd.notna(history):
            estimate=history;method='historical_only';confidence='medium' if len(historical_pairs)>=2 else 'low'
        elif pd.notna(r.get('projected_minutes')):
            estimate=float(r.projected_minutes);method='DAILY_only_unverified';confidence='low'
        else:
            estimate=np.nan;method='no_defensible_estimate';confidence='missing'
        flag=str(r.get('injury_flag','')).upper()
        if flag=='O':estimate=0.;method='contest_out';confidence='excluded'
        rows.append(dict(independent_sources=count,source_spread=spread,historical_minutes=history,adjusted_minutes=estimate,minutes_method=method,confidence=confidence,source_names='; '.join(g.source.astype(str)) if g is not None else ''))
    result=pd.concat([d.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
    result['fppm']=pd.to_numeric(result.projected_fd_points,errors='coerce')/pd.to_numeric(result.projected_minutes,errors='coerce').replace(0,np.nan)
    result['adjusted_fd_points']=result.fppm*result.adjusted_minutes
    result['eligible']=~result.injury_flag.fillna('').astype(str).str.upper().eq('O')
    result['projection_warning']=np.where(result.minutes_method.eq('DAILY_only_unverified'),'DAILY minutes not independently validated',np.where(result.confidence.eq('low'),'Uncertain minutes: scenario test required',''))
    return result

def optimize(pool, number=4, max_overlap=7, exclude_uncertain=False, blocked_pairs=()):
    """Optimize full defensibly projected pool; preserve low-confidence labels, don't silently exclude."""
    a=pool[pool.eligible & pool.adjusted_fd_points.notna() & (pool.adjusted_fd_points>0)].copy()
    if exclude_uncertain:a=a[~a.confidence.isin(['low','missing'])]
    a=a.reset_index(drop=True)
    # Eligibility tokens are separated by '/', but G/F and F/C are composite
    # slots; PG,SG,SF,PF,C determine composite eligibility. Do not split G/F.
    def allowed(eligibility):
        tokens=set(str(eligibility).split('/'))
        allowed_slots=set(tokens)
        if 'G' in tokens or tokens.intersection({'PG','SG'}):allowed_slots.add('G/F')
        if 'F' in tokens or tokens.intersection({'SF','PF','C'}):allowed_slots.add('F/C')
        if 'UTIL' in tokens:allowed_slots.add('UTIL')
        return allowed_slots
    pairs=[(i,j) for i,r in a.iterrows() for j,slot in enumerate(SLOTS) if slot in allowed(r.roster_eligibility)]
    n=len(pairs)
    if not n:raise ValueError('No projected eligible players')
    A=lil_matrix((9+len(a)+1,n))
    for k,(i,j) in enumerate(pairs):A[j,k]=1;A[9+i,k]=1;A[-1,k]=a.iloc[i].salary
    low=np.r_[np.ones(9),np.zeros(len(a)),0];high=np.r_[np.ones(9),np.ones(len(a)),60000]
    sets=[];out=[]
    for t in range(number):
        mat=A.tocsr();lo=low.copy();hi=high.copy();extra=[];elow=[];ehigh=[]
        for s in sets:
            extra.append([1 if i in s else 0 for i,j in pairs]);elow.append(0);ehigh.append(max_overlap)
        for x,y in blocked_pairs:
            inds={i for i,r in a.iterrows() if norm(r.fanduel_name) in (norm(x),norm(y))}
            if len(inds)==2:extra.append([1 if i in inds else 0 for i,j in pairs]);elow.append(0);ehigh.append(1)
        if extra:
            mat=vstack([mat,lil_matrix(np.array(extra)).tocsr()]);lo=np.r_[lo,elow];hi=np.r_[hi,ehigh]
        c=np.array([-float(a.iloc[i].adjusted_fd_points) for i,j in pairs])
        sol=milp(c,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(mat,lo,hi),options={'time_limit':35})
        if sol.x is None:break
        selected=[(SLOTS[j],a.iloc[i]) for k,(i,j) in enumerate(pairs) if sol.x[k]>.5]
        ids={i for k,(i,j) in enumerate(pairs) if sol.x[k]>.5};sets.append(ids)
        assert len(selected)==9 and len({r.fanduel_id for _,r in selected})==9
        assert sum(int(r.salary) for _,r in selected)<=60000
        for slot,r in selected:out.append({'lineup':t+1,'slot':slot,'player':r.fanduel_name,'salary':int(r.salary),'adjusted_minutes':round(float(r.adjusted_minutes),2),'adjusted_fd_points':round(float(r.adjusted_fd_points),2),'confidence':r.confidence,'method':r.minutes_method,'injury_flag':r.injury_flag,'fanduel_id':r.fanduel_id})
    return pd.DataFrame(out)
