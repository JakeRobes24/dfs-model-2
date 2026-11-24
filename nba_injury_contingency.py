"""Bounded pre-tip injury contingency candidates using frozen, reviewed inputs.

The baseline is conditional on uncertain selected players participating.
Single-player OUT scenarios are hypothetical, never official injury news.
Other projections stay unchanged unless the caller supplies reviewed scenario
inputs separately. No probabilities or automatic teammate boosts are inferred.
"""
from time import monotonic
from math import isfinite
import pandas as pd
from model import optimize, SLOTS, allowed_slots
from collections import Counter

UNCERTAIN = {'p','probable','q','questionable','d','doubtful','gtd','day-to-day'}
RESOLVED = {'available','out','inactive','suspended'}

def prepare_contingencies(pool, baseline, *, time_budget_seconds=45,
                          max_scenarios=4, max_overlap=7,
                          exclude_uncertain=False, objective_column='adjusted_fd_points'):
    """Return baseline unchanged plus ranked single-player OUT alternatives.

    Each scenario replaces the entire candidate portfolio, using the original
    objective and overlap constraints. Coverage is explicit; empty/partial
    solves do not replace the baseline. Not a post-lock swap engine.
    """
    if (isinstance(time_budget_seconds,bool) or not isfinite(time_budget_seconds)
            or time_budget_seconds <= 0):
        raise ValueError('Positive finite contingency time budget required')
    if isinstance(max_scenarios,bool) or not isinstance(max_scenarios,int) or max_scenarios < 1:
        raise ValueError('Positive integer max_scenarios required')
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
    scenarios=[]
    for index,(pid,count,_) in enumerate(targets):
        record={'out_id':pid,'player':source.loc[pid,'fanduel_name'],
                'affected_baseline_entries':count,'status':'pending',
                'candidate_count':0,'candidates':pd.DataFrame()}
        remaining=deadline-monotonic()
        if index>=max_scenarios or remaining<=0:
            record['status']='not_run_budget_or_limit'
        else:
            scenario=pool.copy(deep=True)
            scenario.loc[scenario.fanduel_id.eq(pid),'eligible']=False
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
            'completed_scenarios':sum(r['status']=='complete' for r in scenarios),
            'method':'Single-player OUT sensitivity; no teammate role redistribution; not certified live news.'}
