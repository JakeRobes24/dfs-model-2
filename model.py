"""DFS Model 2.0: auditable minutes consensus, confidence and legal FanDuel optimizer."""
import re
import unicodedata
from collections import Counter
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
    if 'player' in h:h['key']=h.player.map(norm);h=h.drop_duplicates('key',keep='last')
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

def allowed_slots(eligibility):
    # Preserve composite slots before splitting the slash-delimited export.
    tokens = set(re.sub(r'(?<![A-Za-z])F/C(?=/|$)', 'F',
                        re.sub(r'(?<![A-Za-z])G/F(?=/|$)', 'G', str(eligibility))).split('/'))
    slots = tokens - {'G', 'F'}
    if 'G' in tokens:
        slots.add('G/F')
    if 'F' in tokens:
        slots.add('F/C')
    return slots


def optimize(pool, number=4, max_overlap=7, exclude_uncertain=False, blocked_pairs=(), *,
             exclude_rosters=(), objective_column="adjusted_fd_points", fixed_slots=None, closed_players=()):
    """Optimize full defensibly projected pool; preserve low-confidence labels, don't silently exclude."""
    a=pool[pool.eligible & pool.adjusted_fd_points.notna() & (pool.adjusted_fd_points>0)].copy()
    if exclude_uncertain:a=a[~a.confidence.isin(['low','missing'])]
    fixed_slots = fixed_slots or {}
    pinned = pool.loc[pool.fanduel_id.isin(fixed_slots.values())]
    if len(pinned) != len(fixed_slots) or not pinned.fanduel_id.is_unique:
        raise ValueError('Locked players must exist exactly once in the contest pool.')
    if any(not isinstance(slot, int) or isinstance(slot, bool) or slot not in range(len(SLOTS))
           for slot in fixed_slots):
        raise ValueError('Locked slots must be valid FanDuel slot indices.')
    if any(SLOTS[slot] not in allowed_slots(row.roster_eligibility)
           for slot, row in ((slot, pinned.loc[pinned.fanduel_id.eq(pid)].iloc[0])
                             for slot, pid in fixed_slots.items())):
        raise ValueError('Locked player is not eligible for the assigned slot.')
    # A started player is immutable even if later ruled out. A newly pinned
    # player in an open game must still pass the ordinary eligibility checks.
    truly_closed = pinned.fanduel_id.isin(set(closed_players))
    invalid_open = pinned.loc[~truly_closed]
    if (not invalid_open.eligible.all() or invalid_open.adjusted_fd_points.isna().any()
            or not np.isfinite(invalid_open.adjusted_fd_points).all()
            or (invalid_open.adjusted_fd_points <= 0).any()):
        raise ValueError('Open-game pinned players require eligible, finite positive projections.')
    # Started-game entries are immutable even when their projection is missing.
    # They contribute zero to the *optimization objective* (see c below);
    # preserve their original NaN in the output rather than fabricating points.
    a = a.loc[~a.fanduel_id.isin(set(closed_players) | set(fixed_slots.values()))]
    if not np.isfinite(a[objective_column]).all():
        raise ValueError('Objective requires finite scores for all optimizable players')
    if fixed_slots:
        a = pd.concat([a, pinned], ignore_index=True)
    if a.fanduel_id.isna().any() or a.fanduel_id.duplicated().any():
        raise ValueError('Optimizer requires unique FanDuel IDs')
    a=a.reset_index(drop=True)
    pinned_ids = set(fixed_slots.values())
    pairs = [
        (i, j) for i, row in a.iterrows() for j, slot in enumerate(SLOTS)
        if slot in allowed_slots(row.roster_eligibility)
        and (fixed_slots[j] == row.fanduel_id if j in fixed_slots else row.fanduel_id not in pinned_ids)
    ]
    n=len(pairs)
    if not n:raise ValueError('No projected eligible players')
    A=lil_matrix((9+len(a)+1,n))
    for k,(i,j) in enumerate(pairs):A[j,k]=1;A[9+i,k]=1;A[-1,k]=a.iloc[i].salary
    low=np.r_[np.ones(9),np.zeros(len(a)),0];high=np.r_[np.ones(9),np.ones(len(a)),60000]
    excluded = [set(roster) for roster in exclude_rosters]
    sets=[];out=[]
    for t in range(number):
        mat=A.tocsr();lo=low.copy();hi=high.copy();extra=[];elow=[];ehigh=[]
        for s in sets:
            extra.append([1 if i in s else 0 for i,j in pairs]);elow.append(0);ehigh.append(max_overlap)
        for roster in excluded:
            extra.append([int(a.iloc[i].fanduel_id in roster) for i,j in pairs])
            elow.append(0)
            ehigh.append(8)
        for x,y in blocked_pairs:
            inds={i for i,r in a.iterrows() if norm(r.fanduel_name) in (norm(x),norm(y))}
            if len(inds)==2:extra.append([1 if i in inds else 0 for i,j in pairs]);elow.append(0);ehigh.append(1)
        if extra:
            mat=vstack([mat,lil_matrix(np.array(extra)).tocsr()]);lo=np.r_[lo,elow];hi=np.r_[hi,ehigh]
        c=np.array([0 if j in fixed_slots else -float(a.iloc[i][objective_column]) for i,j in pairs])
        sol=milp(c,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(mat,lo,hi),options={'time_limit':35})
        if sol.x is None:break
        assignments = [(i, j) for k, (i, j) in enumerate(pairs) if sol.x[k] > .5]
        if fixed_slots or closed_players:
            assignments.sort(key=lambda pair: pair[1])
        selected = [(SLOTS[j], a.iloc[i]) for i, j in assignments]
        ids={i for k,(i,j) in enumerate(pairs) if sol.x[k]>.5};sets.append(ids)
        assert len(selected)==9 and len({r.fanduel_id for _,r in selected})==9
        assert sum(int(r.salary) for _,r in selected)<=60000
        for slot,r in selected:out.append({'lineup':t+1,'slot':slot,'player':r.fanduel_name,'salary':int(r.salary),'adjusted_minutes':round(float(r.adjusted_minutes),2),'adjusted_fd_points':round(float(r.adjusted_fd_points),2),'confidence':r.confidence,'method':r.minutes_method,'injury_flag':r.injury_flag,'fanduel_id':r.fanduel_id,'solver_optimal':sol.status==0})
    return pd.DataFrame(out)


def optimize_late_swap(pool, lineup, closed_players, *, exclude_uncertain=False):
    """Rebuild one entered lineup with started players fixed in their original slots."""
    if not {'slot', 'fanduel_id'} <= set(lineup) or Counter(lineup.slot) != Counter(SLOTS):
        raise ValueError('Provide one lineup with all nine FanDuel slots in entry order.')
    if not lineup.fanduel_id.is_unique or not lineup.fanduel_id.isin(pool.fanduel_id).all():
        raise ValueError('The lineup must have nine unique players from this contest.')
    entries = lineup[['slot', 'fanduel_id']].merge(
        pool[['fanduel_id', 'fanduel_name', 'salary', 'roster_eligibility', 'adjusted_fd_points']],
        on='fanduel_id', validate='one_to_one',
    )
    if (entries.salary.sum() > 60000
            or any(row.slot not in allowed_slots(row.roster_eligibility) for row in entries.itertuples())):
        raise ValueError('The entered lineup exceeds the salary cap or has an invalid slot.')
    # Stable ordering keeps the first and second UTIL rows distinct.
    entries = entries.sort_values('slot', key=lambda slots: slots.map(SLOTS.index), kind='stable').reset_index(drop=True)
    closed_players = set(closed_players)
    if not closed_players:
        raise ValueError('Late swap requires at least one closed contest game.')
    fixed = entries.loc[entries.fanduel_id.isin(closed_players), 'fanduel_id'].to_dict()
    replacement = optimize(pool, number=1, fixed_slots=fixed, closed_players=closed_players,
                           exclude_uncertain=exclude_uncertain)
    if replacement.empty:
        raise ValueError('No legal late-swap lineup fits the locked slots and remaining projected pool.')
    from swap_execution import assign_for_execution
    players = {row.fanduel_id: {'salary': row.salary,
                               'slots': allowed_slots(row.roster_eligibility),
                               'name': row.fanduel_name,
                               'team': getattr(row, 'team', '')}
               for row in pool.itertuples()}
    roster, execution = assign_for_execution(
        entries.fanduel_id.tolist(), replacement.fanduel_id.tolist(),
        players, closed_players)
    replacement = replacement.set_index('fanduel_id').loc[list(roster)].reset_index()
    replacement['slot'] = SLOTS
    sequence = {step['slot']: i+1 for i, step in enumerate(execution['steps'])}
    slot_labels = SLOTS[:7] + ['UTIL 1', 'UTIL 2']
    replacement['execution_order'] = [sequence.get(label, 0) for label in slot_labels]
    replacement['execution_mode'] = execution['mode']
    replacement['team'] = [players[pid]['team'] for pid in roster]
    replacement['entered_team'] = [players[pid]['team'] for pid in entries.fanduel_id]
    locked = replacement.fanduel_id.isin(fixed.values())
    changed = replacement.fanduel_id.ne(entries.fanduel_id)
    original_points = entries.adjusted_fd_points.round(2)
    points_delta = (replacement.adjusted_fd_points - original_points).round(2)
    return replacement.assign(
        locked=locked, changed=changed, entered_player=entries.fanduel_name,
        entered_fanduel_id=entries.fanduel_id, entered_salary=entries.salary, entered_fd_points=original_points,
        fd_points_delta=points_delta.where(changed, 0),
    )
