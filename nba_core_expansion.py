"""Research-only paired comparison: original versus expanded core candidates."""
from datetime import date
import numpy as np
import pandas as pd
from nba_core_challenge import challenge_shared_core
from nba_historical_field import _rosters
from nba_portfolio_stress import stress_portfolio
from nba_simulation import simulate_reviewed_candidates

CORE_CONTROL = 'Original candidates: stressed P90'
CORE_EXPANDED = 'Expanded cores: stressed P90'
CORE_DECLARED = date(2026,11,25)


def build_core_expansion(pool, history, slate, baseline, *, time_budget_seconds=15):
    """Preserve eight baseline candidates, add at most four certified novel cores.

    Simulate once on the entire union, then evaluate both policies with the
    same player draws, stress scenarios and original mean-projection guardrail.
    No target outcomes are supplied to this function.
    """
    frozen = pool.copy()
    frozen['eligible'] = frozen.eligible.astype(str).str.lower().eq('true')
    for col in ('salary','adjusted_fd_points','adjusted_minutes'):
        frozen[col] = pd.to_numeric(frozen[col],errors='coerce')
    frozen = frozen.sort_values('fanduel_id',kind='stable')
    original = _rosters(frozen,baseline,'lineup')
    if (len(original)!=8 or len(set(original.values()))!=8
            or not baseline.solver_optimal.eq(True).all()
            or not baseline.team_rules_verified.eq(True).all()):
        raise ValueError('Core expansion requires eight certified distinct baseline candidates.')
    # Challenge the four projection-ranked entries, not a target-outcome core.
    points = frozen.set_index('fanduel_id').adjusted_fd_points
    means = {label:float(points.loc[sorted(ids)].sum()) for label,ids in original.items()}
    top = sorted(means,key=lambda label:(-means[label],label))[:4]
    reference = float(np.mean([means[label] for label in top]))
    audit, extra = challenge_shared_core(frozen,baseline.loc[baseline.lineup.isin(top)],
                                        time_budget_seconds=time_budget_seconds)
    if not audit.empty and not audit.Status.str.startswith('Certified').all():
        raise ValueError('Core expansion incomplete: at least one scenario not certified.')
    known = set(original.values())
    additions = []
    if not extra.empty:
        for _, group in extra.groupby('lineup',sort=True):
            ids = frozenset(group.fanduel_id)
            if ids not in known:
                additions.append(group.assign(lineup=max(original)+len(additions)+1))
                known.add(ids)
    union = pd.concat([baseline,*additions],ignore_index=True)
    _rosters(frozen,union,'lineup')
    ranges,_,_,draws = simulate_reviewed_candidates(history,frozen,union,slate,return_draws=True)
    control, control_table = stress_portfolio(draws,frozen,baseline,
        ranges.loc[ranges.lineup.isin(original)],reference_mean=reference)
    expanded, expanded_table = stress_portfolio(draws,frozen,union,ranges,reference_mean=reference)
    before = control_table.iloc[0]
    after = expanded_table.iloc[0]
    if after['Worst-scenario best P90'] < before['Worst-scenario best P90'] - 1e-8:
        raise ValueError('Expanded feasible set lost its original control.')
    metrics = {'New core candidates':len(additions),
               'New cores selected':sum(label not in original for label in expanded),
               'Simulated best P90 change':after['Worst-scenario best P90']-before['Worst-scenario best P90'],
               'Simulated best P10 change':after['Worst-scenario best P10']-before['Worst-scenario best P10'],
               'Average projected FD change':after['Average projected FD']-before['Average projected FD'],
               'All-entry shared players change':after['All-entry shared players']-before['All-entry shared players']}
    return union,{CORE_CONTROL:control,CORE_EXPANDED:expanded},metrics


def score_core_expansion(pool, rosters, selections, results, slate):
    """Reuse the existing exact-roster/official-outcome scoring validation."""
    from nba_candidate_experiment import score_experiment
    if set(selections)!={CORE_CONTROL,CORE_EXPANDED}:
        raise ValueError('Both paired core policies required.')
    report,_ = score_experiment(pool,rosters,{'Projection ranked':selections[CORE_CONTROL],
        'Simulated P90 ranked':selections[CORE_EXPANDED]},results,slate)
    report['Policy'] = report.Policy.map({'Projection ranked':CORE_CONTROL,
                                        'Simulated P90 ranked':CORE_EXPANDED})
    report['Period'] = 'Prospective' if slate>CORE_DECLARED else 'Exploratory'
    return report
