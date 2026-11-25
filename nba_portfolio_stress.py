"""Fixed research-only equal-budget portfolio selection under dependence stress.

No estimated contest win probabilities, no forced exposure cap and no changes
to the live optimizer. Each candidate uses the same shared player outcomes.
"""
from itertools import combinations
from datetime import date
import numpy as np
import pandas as pd
from nba_candidate_sensitivity import SCENARIOS, correlated_draws

STRESS_POLICY = 'Dependence-stressed portfolio P90'
STRESS_DECLARED = date(2026,11,25)
MAX_AVERAGE_PROJECTION_LOSS = 2.0


def stress_portfolio(outcomes, pool, rosters, ranges, *, entries=4, reference_mean=None):
    """Enumerate four of eight candidates; optimize worst-scenario best-entry P90.

    A fixed, exploratory mean projection guardrail allows at most two FD
    points per entry below the projection-ranked portfolio. P10 of the best
    entry and exposure metrics are diagnostics, not optimization targets.
    """
    if not {'lineup','reviewed_fd'} <= set(ranges) or not ranges.lineup.is_unique:
        raise ValueError('Unique candidate projection summaries required.')
    labels = sorted(ranges.lineup.tolist())
    if len(labels) > 12 or not 1 <= entries <= len(labels):
        raise ValueError('Use a bounded candidate set and feasible equal entry budget.')
    if set(labels) != set(rosters.lineup) or rosters.fanduel_id.isna().any():
        raise ValueError('Candidate identities must match the simulation.')
    membership = {label: frozenset(rosters.loc[rosters.lineup.eq(label),'fanduel_id'])
                  for label in labels}
    if any(len(ids)!=9 for ids in membership.values()) or len(set(membership.values())) != len(labels):
        raise ValueError('Supply distinct nine-player candidate rosters.')
    projected = pd.to_numeric(ranges.set_index('lineup').reviewed_fd.reindex(labels),errors='coerce').to_numpy()
    if not np.isfinite(projected).all():
        raise ValueError('Finite reviewed projections required.')
    best_mean = np.sort(projected)[-entries:].mean()
    baseline = best_mean if reference_mean is None else float(reference_mean)
    if not np.isfinite(baseline) or baseline > best_mean + 1e-9:
        raise ValueError('Invalid common projection reference.')
    matrices = {}
    for scenario in SCENARIOS:
        totals = correlated_draws(outcomes,pool,scenario)._lineup_totals(rosters)
        matrix = np.column_stack([totals[label] for label in labels])
        if not len(matrix) or not np.isfinite(matrix).all():
            raise ValueError('Complete finite shared simulation draws required.')
        matrices[scenario] = matrix
    rows = []
    for indices in combinations(range(len(labels)),entries):
        ix = list(indices)
        mean = float(projected[ix].mean())
        if mean < baseline - MAX_AVERAGE_PROJECTION_LOSS - 1e-9:
            continue
        ids = [labels[i] for i in indices]
        p10s,p90s,mean_best = [],[],[]
        for matrix in matrices.values():
            best = matrix[:,ix].max(axis=1)
            p10,p90 = np.quantile(best,[.1,.9])
            p10s.append(float(p10)); p90s.append(float(p90)); mean_best.append(float(best.mean()))
        shared = [len(membership[a]&membership[b]) for a,b in combinations(ids,2)]
        core = len(set.intersection(*(set(membership[label]) for label in ids)))
        rows.append({'Candidates':tuple(ids),'Average projected FD':mean,
                     'Projection loss per entry':baseline-mean,
                     'Worst-scenario best P90':min(p90s),
                     'Worst-scenario best P10':min(p10s),
                     'Mean scenario best FD':float(np.mean(mean_best)),
                     'Average shared players':float(np.mean(shared)) if shared else 0.,
                     'All-entry shared players':core})
    report = pd.DataFrame(rows).sort_values(
        ['Worst-scenario best P90','Average projected FD','Candidates'],
        ascending=[False,False,True],kind='stable').reset_index(drop=True)
    return list(report.iloc[0]['Candidates']),report
