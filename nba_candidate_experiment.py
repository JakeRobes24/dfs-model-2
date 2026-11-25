"""Controlled retrospective comparison of two fixed candidate-ranking policies.

Both policies choose four from the same eight projection-optimized rosters.
Simulation is trained only on earlier frozen outcomes. Target results are
accepted only by the separate scoring function, never by candidate selection.
"""
from datetime import date

import numpy as np
import pandas as pd

from model import optimize
from nba_historical_field import _rosters
from nba_simulation import simulate_reviewed_candidates
from slate_replay_capture import build_replay_rows
from nba_portfolio_stress import stress_portfolio, STRESS_POLICY, STRESS_DECLARED

DECLARED = date(2026, 11, 24)
CANDIDATES = 8
ENTRIES = 4


def select_portfolios(ranges, *, entries=ENTRIES):
    required = {'lineup', 'reviewed_fd', 'fd_p90'}
    if not required <= set(ranges) or ranges.lineup.isna().any() or not ranges.lineup.is_unique:
        raise ValueError('Use one simulation summary per unique candidate.')
    if not 1 <= entries <= len(ranges):
        raise ValueError('Insufficient candidates for equal-sized portfolios.')
    numeric = ranges[['reviewed_fd','fd_p90']].apply(pd.to_numeric, errors='coerce')
    if not np.isfinite(numeric).all().all():
        raise ValueError('All candidate forecasts must be finite.')
    ranked = ranges.assign(**numeric).sort_values(
        ['reviewed_fd','lineup'], ascending=[False,True], kind='stable')
    ceiling = ranked.sort_values(['fd_p90','reviewed_fd','lineup'],
                                 ascending=[False,False,True], kind='stable')
    return {'Projection ranked': ranked.lineup.head(entries).tolist(),
            'Simulated P90 ranked': ceiling.lineup.head(entries).tolist()}


def build_experiment(pool, history, slate, *, time_budget_seconds=45):
    """Generate candidates from the frozen pool; never use target actuals."""
    empty = pd.DataFrame(columns=['fanduel_id','outcome','nba_actual_minutes',
                                  'nba_fd_points','nba_source','recorded_fd_points'])
    build_replay_rows(pool, empty, slate)
    needed = {'salary','roster_eligibility','confidence','minutes_method','injury_flag'}
    if not needed <= set(pool):
        raise ValueError('Frozen pool lacks optimizer metadata.')
    frozen = pool.copy()
    frozen['eligible'] = frozen.eligible.astype(str).str.lower().eq('true')
    for column in ('salary','adjusted_fd_points','adjusted_minutes'):
        frozen[column] = pd.to_numeric(frozen[column], errors='coerce')
    selectable = frozen.eligible & frozen.adjusted_fd_points.gt(0)
    if not frozen.loc[selectable,'salary'].between(1,60000).all():
        raise ValueError('Invalid frozen contest salary.')
    frozen = frozen.sort_values('fanduel_id', kind='stable')
    rosters = optimize(frozen, number=CANDIDATES, max_overlap=7,
                       time_budget_seconds=time_budget_seconds)
    if (rosters.empty or rosters.lineup.nunique() != CANDIDATES
            or not rosters.solver_optimal.all() or not rosters.team_rules_verified.all()):
        raise ValueError('Eight certified optimal candidates were not available within the solve budget.')
    _rosters(frozen, rosters, 'lineup')
    ranges, _, training_count, draws = simulate_reviewed_candidates(
        history, frozen, rosters, slate, return_draws=True)
    selected = select_portfolios(ranges)
    selected[STRESS_POLICY], _ = stress_portfolio(draws, frozen, rosters, ranges)
    return rosters, ranges, selected, training_count


def score_experiment(pool, rosters, selections, results, slate):
    """Score both fixed portfolios against identical verified official outcomes."""
    sets = _rosters(pool, rosters, 'lineup')
    original = {'Projection ranked','Simulated P90 ranked'}
    if set(selections) not in (original, original | {STRESS_POLICY}):
        raise ValueError('Expected the fixed portfolio policies.')
    for labels in selections.values():
        if len(labels) != ENTRIES or len(set(labels)) != ENTRIES or not set(labels) <= sets.keys():
            raise ValueError('Both policies must select four distinct supplied candidates.')
    if not {'fanduel_id','outcome','nba_source','nba_fd_points'} <= set(results) or not results.fanduel_id.is_unique:
        raise ValueError('Unique verified official results required.')
    source = results.nba_source.fillna('').astype(str).str.strip().ne('')
    actual = pd.to_numeric(results.nba_fd_points, errors='coerce')
    played = source & results.outcome.eq('Played') & np.isfinite(actual)
    dnp = source & results.outcome.eq('Did not play')
    points = dict(zip(results.loc[played|dnp,'fanduel_id'], actual.mask(dnp,0)[played|dnp]))
    required = set().union(*sets.values())
    if not required <= points.keys():
        raise ValueError('At least one candidate outcome remains unresolved; no paired evaluation.')
    totals = {label: round(sum(points[pid] for pid in sorted(ids)),1) for label,ids in sets.items()}
    reports = []
    for policy, labels in selections.items():
        values = [totals[label] for label in labels]
        reports.append({'Policy': policy, 'Date': slate.isoformat(),
                        'Period': 'Prospective' if slate > (STRESS_DECLARED if policy == STRESS_POLICY else DECLARED) else 'Exploratory',
                        'Entries': len(labels), 'Selected candidates': ', '.join(map(str,labels)),
                        'Best actual FD': max(values), 'Average actual FD': np.mean(values),
                        'Worst actual FD': min(values)})
    return pd.DataFrame(reports), pd.DataFrame({'lineup':list(totals),'actual_fd':list(totals.values())})
