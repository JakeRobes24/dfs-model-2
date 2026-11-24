"""Audit proposed FanDuel lineups and find distinct legal alternatives."""
from collections import Counter

import numpy as np
import pandas as pd

from model import SLOTS, allowed_slots, optimize
from nba_classic_rules import validate_team_roster


def challenge_lineups(pool, proposed, *, include_ceiling=False, exclude_uncertain=False):
    required = {'lineup', 'slot', 'fanduel_id'}
    missing = required - set(proposed.columns)
    if missing or proposed.empty or proposed[list(required)].isna().any().any():
        raise ValueError('Proposed CSV must have nonempty lineup, slot and fanduel_id columns')
    if pool.fanduel_id.isna().any() or pool.fanduel_id.duplicated().any():
        raise ValueError('Pool requires unique FanDuel IDs')
    pool = pool.set_index('fanduel_id', drop=False)
    eligible = pool[pool.eligible & pool.adjusted_fd_points.gt(0)]
    if exclude_uncertain:
        eligible = eligible[~eligible.confidence.isin(['low', 'missing'])]
    objectives = ['adjusted_fd_points']
    if include_ceiling:
        if 'ceiling_fd_points' not in eligible:
            raise ValueError('Ceiling comparison requires a researched ceiling_fd_points column')
        ceilings = pd.to_numeric(eligible.ceiling_fd_points, errors='coerce')
        if not (np.isfinite(ceilings) & ceilings.ge(eligible.adjusted_fd_points)).all():
            raise ValueError('Ceilings must cover the optimizable pool and be at least the adjusted projection')
        eligible = eligible.assign(ceiling_fd_points=ceilings)
        objectives.append('ceiling_fd_points')

    audits, summaries, alternatives = [], [], []
    for label, group in proposed.groupby('lineup', sort=False):
        ids = set(group.fanduel_id)
        errors = []
        if len(ids) != 9 or Counter(group.slot) != Counter(SLOTS):
            errors.append('Roster requires nine unique players and all nine slots')
        for row in group.itertuples():
            if row.fanduel_id not in pool.index:
                errors.append(f'{row.fanduel_id}: not on contest slate')
            elif row.fanduel_id not in eligible.index:
                errors.append(f'{row.fanduel_id}: ineligible or missing projection')
            elif row.slot not in allowed_slots(pool.at[row.fanduel_id, 'roster_eligibility']):
                errors.append(f'{row.fanduel_id}: not eligible for {row.slot}')
        distinct = pool.loc[pool.index.isin(ids)]
        salary = int(distinct.salary.sum()) if len(distinct) == 9 else None
        if salary is not None and salary > 60000:
            errors.append('Salary exceeds $60,000')
        if len(distinct) == 9:
            try:
                if not validate_team_roster(pool, distinct.fanduel_id):
                    errors.append('Team restrictions unverified: legacy pool has no team data')
            except ValueError as exc:
                errors.append(str(exc))
        known = group[['lineup', 'slot', 'fanduel_id']].join(pool[['fanduel_name', 'adjusted_fd_points', 'prelock_change']]
                          if 'prelock_change' in pool else pool[['fanduel_name', 'adjusted_fd_points']],
                          on='fanduel_id')
        audits.append(known)
        for objective in objectives:
            best = optimize(eligible.reset_index(drop=True), number=1,
                            exclude_rosters=(ids,), objective_column=objective) if len(eligible) >= 9 else pd.DataFrame()
            best_ids = best.fanduel_id.tolist() if not best.empty else []
            base_score = float(eligible.loc[list(ids), objective].sum()) if not errors else None
            best_score = float(eligible.loc[best_ids, objective].sum()) if best_ids else None
            summaries.append(dict(lineup=label, objective=objective, proposed_salary=salary,
                                  proposed_score=base_score, alternative_score=best_score,
                                  difference=best_score - base_score if best_score is not None and base_score is not None else None,
                                  alternative_salary=int(best.salary.sum()) if best_ids else None,
                                  alternative_optimal=bool(best.solver_optimal.all()) if best_ids else False,
                                  issues=' | '.join(errors)))
            if best_ids:
                alternatives.append(best.assign(proposed_lineup=label, objective=objective))
    return (pd.concat(audits, ignore_index=True), pd.DataFrame(summaries),
            pd.concat(alternatives, ignore_index=True) if alternatives else pd.DataFrame())
