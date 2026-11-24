"""Bounded pre-tip injury contingency candidates using frozen, reviewed inputs.

The baseline is conditional on uncertain selected players participating.
Single-player and paired OUT scenarios are hypothetical, never official injury news.
Other projections stay unchanged unless the caller supplies reviewed scenario
inputs separately. No probabilities or automatic teammate boosts are inferred.
"""
from time import monotonic
from math import isfinite
import pandas as pd
from model import optimize, SLOTS, allowed_slots
from collections import Counter
from itertools import combinations

UNCERTAIN = {'p','probable','q','questionable','d','doubtful','gtd','day-to-day'}
RESOLVED = {'available','out','inactive','suspended'}

def prepare_contingencies(pool, baseline, *, time_budget_seconds=45,
                          max_scenarios=4, max_overlap=7,
                          exclude_uncertain=False, objective_column='adjusted_fd_points',
                          max_joint_scenarios=0):
    """Return baseline unchanged plus ranked single-player and optional paired OUT alternatives.

    Each scenario replaces the entire candidate portfolio, using the original
    objective and overlap constraints. Coverage is explicit; empty/partial
    solves do not replace the baseline. Not a post-lock swap engine.
    """
    if (isinstance(time_budget_seconds,bool) or not isfinite(time_budget_seconds)
            or time_budget_seconds <= 0):
        raise ValueError('Positive finite contingency time budget required')
    if isinstance(max_scenarios,bool) or not isinstance(max_scenarios,int) or max_scenarios < 1:
        raise ValueError('Positive integer max_scenarios required')
    if isinstance(max_joint_scenarios,bool) or not isinstance(max_joint_scenarios,int) or max_joint_scenarios < 0:
        raise ValueError('Nonnegative integer joint scenario limit required')
    deadline = monotonic() + time_budget_seconds
    if not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any():
        raise ValueError('Unique contest IDs required')
    if baseline.empty:
        raise ValueError('A nonempty baseline is required')
    source=pool.set_index('fanduel_id')
    groups=list(baseline.groupby('lineup'))
    for _, roster in groups:
        if (Counter(roster.slot)!=Counter(SLOTS) or not roster.fanduel_id.is_unique
                or not roster.fanduel_id.isin(source.index).all()):
            raise ValueError('Invalid baseline roster')
        rows=source.loc[roster.fanduel_id]
        if (not rows.eligible.all() or rows.salary.sum()>60000
                or any(s not in allowed_slots(e) for s,e in zip(roster.slot,rows.roster_eligibility))):
            raise ValueError('Baseline contains ineligible player, slot or salary')
    exposure=baseline.fanduel_id.value_counts()
    targets=[]
    for pid,count in exposure.items():
        row=source.loc[pid]
        official=str(row.get('prelock_status','')).strip().casefold()
        contest=str(row.get('injury_flag','')).strip().casefold()
        if official in RESOLVED:
            continue
        if official in UNCERTAIN or contest in UNCERTAIN:
            targets.append((pid,int(count),float(row.adjusted_fd_points)))
    targets.sort(key=lambda t:(-t[1],-t[2],str(t[0])))
    # Singles retain priority; a separate bounded joint budget is optional.
    singles=[(pid,) for pid,_,_ in targets]
    # Consider only selected uncertain players for these hypothetical pairs.
    # Pair priority is unique entries affected, then aggregate exposure.
    memberships={pid:set(baseline.loc[baseline.fanduel_id.eq(pid),'lineup']) for pid in exposure.index}
    pairs=sorted(combinations((pid for pid,_,_ in targets),2),
                 key=lambda ids:(-len(set().union(*(memberships[p] for p in ids))),
                                 -sum(len(memberships[p]) for p in ids),tuple(map(str,ids))))
    scenarios=[]
    requested=singles + pairs[:max_joint_scenarios]
    for index,out_ids in enumerate(requested):
        pid=out_ids[0] if len(out_ids)==1 else '+'.join(map(str,out_ids))
        count=len(set().union(*(memberships[p] for p in out_ids)))
        record={'out_id':pid,'player':' + '.join(str(source.loc[p,'fanduel_name']) for p in out_ids),
                'out_ids':out_ids,
                'affected_baseline_entries':count,'status':'pending',
                'candidate_count':0,'candidates':pd.DataFrame()}
        remaining=deadline-monotonic()
        if (len(out_ids)==1 and index>=max_scenarios) or remaining<=0:
            record['status']='not_run_budget_or_limit'
        else:
            scenario=pool.copy(deep=True)
            scenario.loc[scenario.fanduel_id.isin(out_ids),'eligible']=False
            try:
                candidates=optimize(scenario, number=len(groups), max_overlap=max_overlap,
                    exclude_uncertain=exclude_uncertain, objective_column=objective_column,
                    time_budget_seconds=remaining)
            except ValueError as exc:
                record['status']='unavailable'
                record['reason']=str(exc)
            else:
                count_found=0 if candidates.empty else candidates.lineup.nunique()
                record.update(candidate_count=count_found,candidates=candidates,
                    status='complete' if count_found==len(groups) else 'partial_or_infeasible')
        scenarios.append(record)
    return {'baseline':baseline.copy(deep=True), 'scenarios':scenarios,
            'uncertain_selected_players':len(targets),
            'completed_scenarios':sum(r['status']=='complete' and len(r['out_ids'])==1 for r in scenarios),
            'joint_scenarios_possible':len(pairs),
            'joint_scenarios_requested':min(max_joint_scenarios,len(pairs)),
            'joint_scenarios_completed':sum(r['status']=='complete' and len(r['out_ids'])==2 for r in scenarios),
            'method':'Hypothetical single-player and optional paired OUT sensitivity; no automatic teammate redistribution; not certified live news.'}
