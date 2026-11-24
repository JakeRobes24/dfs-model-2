"""Connect saved hypothetical NBA scratch candidates to current entered rosters.

A preview is not live news. Activation requires a current reviewed official
status audit and a verified lock snapshot supplied by the caller.
"""
from math import isfinite
from collections import Counter
import pandas as pd
from model import SLOTS, allowed_slots
from nba_swap_execution import find_executable_layout

OUT={'out','inactive','suspended'}

def ordered_ids(roster):
    if Counter(roster.slot)!=Counter(SLOTS) or not roster.fanduel_id.is_unique:
        raise ValueError('Entry must have all nine slots and distinct exact contest IDs')
    return tuple(roster.sort_values('slot',key=lambda x:x.map(SLOTS.index),
                                    kind='stable').fanduel_id)

def _confirmed_out(audit, pid, cutoff, max_age_hours):
    required={'fanduel_id','official','status','source','observed_at','review'}
    if audit is None or not required<=set(audit.columns):
        return False
    notes=audit.loc[audit.fanduel_id.eq(pid) & audit.official.eq(True)
                    & audit.review.eq('Reviewed') & audit.source.fillna('').ne('')].copy()
    notes['stamp']=pd.to_datetime(notes.observed_at,utc=True,errors='coerce')
    notes=notes.loc[notes.stamp.between(cutoff-pd.Timedelta(hours=max_age_hours),cutoff)]
    notes['decision']=notes.status.astype(str).str.strip().str.casefold()
    notes=notes.loc[notes.decision.isin(OUT|{'available','probable','questionable','doubtful'})]
    if notes.empty:
        return False
    latest=notes.loc[notes.stamp.eq(notes.stamp.max()),'decision']
    return latest.nunique()==1 and latest.iloc[0] in OUT

def plan_contingency_entry(pool, entered, candidates, out_ids, *, closed_players=(),
                           preview=True, schedule_verified=False, audit=None,
                           as_of=None, max_age_hours=6):
    """Rank legal executable prepared candidates for one exact current entry.

    Re-score with the current pool; never assume the old conditional scores
    are still valid. Keep incomplete or stale candidates out of the result.
    No automatic entry, no inferred news, no replacement of a locked slot.
    """
    if not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any():
        raise ValueError('Unique contest IDs required')
    before=ordered_ids(entered)
    lookup=pool.set_index('fanduel_id')
    closed=set(closed_players)
    out_ids=tuple(out_ids)
    if not out_ids or len(out_ids)!=len(set(out_ids)):
        raise ValueError('Distinct scratch IDs required')
    if not (set(before)|closed|set(out_ids))<=set(lookup.index):
        raise ValueError('Unknown contest ID')
    if sum(lookup.loc[list(before),'salary'])>60000 or any(
            s not in allowed_slots(lookup.at[p,'roster_eligibility']) for s,p in zip(SLOTS,before)):
        raise ValueError('Invalid current entry')
    if not preview:
        cutoff=pd.Timestamp(as_of)
        if (not schedule_verified or as_of is None or pd.isna(cutoff)
                or cutoff.tzinfo is None or not isfinite(max_age_hours) or max_age_hours<=0):
            raise ValueError('Live activation requires verified locks and a dated status audit')
        if not all(_confirmed_out(audit,p,cutoff,max_age_hours) for p in out_ids):
            raise ValueError('Scratch scenario is not confirmed by current official evidence')
    current=pool.copy(deep=True)
    current.loc[current.fanduel_id.isin(out_ids),'eligible']=False
    if set(before)&closed&set(out_ids):
        return {'status':'blocked_locked_scratch','options':[]}
    # Only candidates with a valid current pool, including all retained open
    # players, can become options. A locked ineligible player is immutable.
    options=[]
    if candidates.empty:
        return {'status':'no_executable_candidate','options':[]}
    for label,roster in candidates.groupby('lineup',sort=False):
        try:
            target=ordered_ids(roster)
            if not set(target)<=set(lookup.index) or set(target)&set(out_ids):
                continue
            if any((p in closed and target[i]!=p) or
                   (target[i] in closed and target[i]!=p) for i,p in enumerate(before)):
                continue
            opened=[p for p in target if p not in closed]
            rows=current.set_index('fanduel_id').loc[opened]
            if not rows.eligible.all() or not rows.adjusted_fd_points.map(
                    lambda v:pd.notna(v) and isfinite(float(v)) and float(v)>0).all():
                continue
            layout,steps=find_executable_layout(current,before,target,closed)
            if steps is None:
                continue
        except (ValueError,KeyError,TypeError):
            continue
        values=lookup.loc[list(layout),'adjusted_fd_points']
        total=float(values.sum()) if values.notna().all() and values.map(isfinite).all() else None
        options.append({'candidate':label,'ordered_ids':layout,'steps':steps,
                        'current_fd_points':total,'salary':int(lookup.loc[list(layout),'salary'].sum())})
    options.sort(key=lambda r:(r['current_fd_points'] is None,
                             -(r['current_fd_points'] or 0),len(r['steps']),str(r['candidate'])))
    return {'status':('hypothetical_preview' if preview else 'validated_at_snapshot') if options
            else 'no_executable_candidate','options':options}
