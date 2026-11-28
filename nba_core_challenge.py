"""Bounded counterfactual core audit; never changes live portfolio selection."""
from collections import Counter
from time import monotonic
from math import isfinite
import pandas as pd
from model import optimize
from nba_historical_field import _rosters


def challenge_shared_core(pool, baseline, *, max_players=3, time_budget_seconds=15,
                          exclude_uncertain=False, objective_column='adjusted_fd_points',
                          expanded=False):
    """Compare best legal roster with selected heavily shared players omitted.

    Choose targets from the existing portfolio, before seeing outcomes.
    Single exclusions and one joint exclusion test how costly alternative
    cores are. No injured-player claim or mandatory exposure rule is implied.
    An incomplete or uncertified solve is reported rather than accepted.
    """
    if (type(max_players) is not int or not 1 <= max_players <= (9 if expanded else 3)
            or isinstance(time_budget_seconds,bool) or not isfinite(time_budget_seconds)
            or not 0 < time_budget_seconds <= 45):
        raise ValueError('Use a bounded core challenge budget and one to three targets (up to nine in expanded review).')
    if pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique:
        raise ValueError('Use the authoritative unique contest pool.')
    roster_sets = _rosters(pool,baseline,'lineup')
    if len(roster_sets) < 2 or len(set(roster_sets.values())) != len(roster_sets):
        raise ValueError('Core review requires at least two distinct legal candidates.')
    lookup = pool.set_index('fanduel_id')
    all_ids = set().union(*roster_sets.values())
    active = lookup.loc[sorted(all_ids)]
    eligible = active.eligible.astype(str).str.lower().eq('true')
    means = pd.to_numeric(active.adjusted_fd_points,errors='coerce')
    objective = pd.to_numeric(active[objective_column],errors='coerce')
    if (not eligible.all() or not means.gt(0).all()
            or not means.map(isfinite).all() or not objective.map(isfinite).all()
            or (exclude_uncertain and active.confidence.isin(['low','missing']).any())):
        raise ValueError('Baseline is no longer eligible or has invalid projections.')
    baseline_best = max(float(means.loc[sorted(ids)].sum()) for ids in roster_sets.values())
    baseline_objective = max(float(objective.loc[sorted(ids)].sum()) for ids in roster_sets.values())
    exposure = Counter(pid for ids in roster_sets.values() for pid in ids)
    unreviewed = []
    if expanded:
        from exposure_challenge_plan import exposure_challenge_plan
        plan = exposure_challenge_plan(roster_sets.values(),max_targets=max_players,
                                      priority=means.to_dict())
        scenarios = plan['scenarios']
        unreviewed = plan['unreviewed_targets']
    else:
        targets = sorted((pid for pid,count in exposure.items() if count >= 2),
                         key=lambda pid:(-exposure[pid],-means.loc[pid],str(pid)))[:max_players]
        scenarios = [(pid,) for pid in targets]
        if len(targets)>=2:
            scenarios.append(tuple(targets[:2]))
    deadline = monotonic()+time_budget_seconds
    records, alternatives = [], []
    known = set(roster_sets.values())
    for idx, omitted in enumerate(scenarios,1):
        row = {'Scenario':idx,'Omitted IDs':' | '.join(map(str,omitted)),
               'Omitted players':' | '.join(str(lookup.loc[pid,'fanduel_name']) for pid in omitted),
               'Affected baseline entries':sum(bool(set(omitted)&ids) for ids in roster_sets.values()),
               'Best baseline FD':baseline_best,'Best baseline objective':baseline_objective,
               'Status':'Not run: budget exhausted'}
        remaining = deadline-monotonic()
        if remaining <= 0:
            records.append(row); continue
        # Give each planned scenario a share of the remaining budget.
        restricted = pool.copy(deep=True)
        restricted['eligible'] = restricted.eligible.astype(str).str.lower().eq('true')
        restricted.loc[restricted.fanduel_id.isin(omitted),'eligible'] = False
        try:
            candidate = optimize(restricted,number=1,exclude_uncertain=exclude_uncertain,
                                 objective_column=objective_column,
                                 time_budget_seconds=remaining/(len(scenarios)-idx+1))
            if candidate.empty:
                row['Status'] = 'No candidate returned: infeasible or budget'
            elif not candidate.solver_optimal.all() or not candidate.team_rules_verified.all():
                row['Status'] = 'Candidate not certified optimal'
            else:
                ids = next(iter(_rosters(pool,candidate,'lineup').values()))
                if set(omitted)&ids or not restricted.set_index('fanduel_id').loc[sorted(ids),'eligible'].all():
                    raise ValueError('Candidate violates exclusion or eligibility.')
                points = float(lookup.loc[sorted(ids),'adjusted_fd_points'].sum())
                score = float(lookup.loc[sorted(ids),objective_column].sum())
                novel = ids not in known
                row.update({'Status':'Certified distinct alternative' if novel else 'Certified already represented',
                            'Alternative FD':points,'FD gap vs best baseline':points-baseline_best,
                            'Alternative objective':score,'Objective gap vs best baseline':score-baseline_objective,
                            'Max shared with baseline':max(len(ids&existing) for existing in roster_sets.values()),
                            'New roster':novel})
                if novel:
                    alternatives.append(candidate.assign(lineup=idx,core_scenario=idx))
                    known.add(ids)
        except (ValueError,TypeError,KeyError) as exc:
            row['Status'] = f'Unavailable: {exc}'
        records.append(row)
    for pid in unreviewed:
        records.append({'Scenario':len(records)+1,'Omitted IDs':str(pid),
                        'Omitted players':str(lookup.loc[pid,'fanduel_name']),
                        'Affected baseline entries':exposure[pid],
                        'Status':'Not run: target limit'})
    return pd.DataFrame(records), (pd.concat(alternatives,ignore_index=True) if alternatives else pd.DataFrame())
