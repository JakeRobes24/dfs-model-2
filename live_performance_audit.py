"""Read-only matched forecast and lineup diagnostics for archived DFS slates."""
from collections import Counter
import numpy as np
import pandas as pd

KEY = ['sport', 'date', 'contest', 'id']


def validate_pool(pool):
    if pool[KEY].isna().any().any() or pool.duplicated(KEY).any():
        raise ValueError('Duplicate or incomplete contest identities.')
    prefix = pool.id.str.split('-', n=1).str[0]
    if not prefix.eq(pool.contest).all() or not pool.id.str.fullmatch(r'\d+-\d+').all():
        raise ValueError('Player ID must belong to its exact contest.')


def _usable(pool, fields):
    return pool.loc[np.isfinite(pool[list(fields)]).all(axis=1)]


def paired_errors(pool, forecasts):
    """Use one common complete-case sample for every specified forecast."""
    rows = _usable(pool, ['actual', *forecasts])
    summary = {}
    for column in forecasts:
        error = rows[column]-rows.actual
        if not error.empty:
            summary[column] = dict(n=len(error), bias=error.mean(),
                                   mae=error.abs().mean(), rmse=np.sqrt((error**2).mean()))
    return summary


def selection_errors(pool, stage):
    """Compare selected and nonselected players and exact coarse pregame strata."""
    rows = _usable(pool, ['actual', stage, 'salary']).copy()
    rows['error'] = rows[stage]-rows.actual
    rows['salary_band'] = rows.salary.floordiv(1000)
    rows['projection_band'] = rows[stage].floordiv(5)
    picked = rows.loc[rows.exposure.gt(0)]
    other = rows.loc[rows.exposure.eq(0)]
    cells = ['salary_band', 'projection_band']
    controls = other.groupby(cells).error.agg(control_bias='mean', controls='size').reset_index()
    matched = picked.merge(controls, on=cells, validate='many_to_one')
    exposure = picked.exposure.sum()
    return dict(selected=paired_errors(picked, [stage]), other=paired_errors(other, [stage]),
                exposure_slots=int(exposure),
                exposure_weighted_bias=float((picked.error*picked.exposure).sum()/exposure) if exposure else None,
                matched_selected=len(matched),
                matched_cells=len(matched[cells].drop_duplicates()),
                matched_bias_gap=float((matched.error-matched.control_bias).mean()) if len(matched) else None)


def minute_rate_errors(pool, points, minutes):
    """Exact midpoint decomposition of forecast-minus-actual FD error."""
    rows = _usable(pool, ['actual', 'actual_minutes', points, minutes])
    rows = rows.loc[rows[minutes].gt(0) & rows.actual_minutes.gt(0)].copy()
    observed_rate = rows.actual/rows.actual_minutes
    forecast_rate = rows[points]/rows[minutes]
    rows['minute_error'] = rows[minutes]-rows.actual_minutes
    rows['rate_error'] = forecast_rate-observed_rate
    rows['minute_effect'] = rows.minute_error*(observed_rate+forecast_rate)/2
    rows['rate_effect'] = rows.rate_error*(rows[minutes]+rows.actual_minutes)/2
    return rows


def compare_saved_rosters(pool, candidates, *, slots):
    """Resolve exact IDs and avoid crediting unknown outcomes with zero."""
    if pool.id.duplicated().any() or pool.contest.nunique() != 1:
        raise ValueError('Roster scoring requires one exact contest pool.')
    by_id = pool.set_index('id')
    results = []
    for label, ids in candidates.items():
        if len(ids) != slots or len(set(ids)) != slots or set(ids)-set(by_id.index):
            raise ValueError(f'Inconsistent archived roster: {label}.')
        rows = by_id.loc[ids]
        known = np.isfinite(rows.actual).all()
        results.append(dict(label=label, actual=float(rows.actual.sum()) if known else None,
                            known_slots=int(np.isfinite(rows.actual).sum())))
    return results


def roster_exposure(candidates):
    counts = Counter(player for ids in candidates.values() for player in set(ids))
    overlaps = [len(set(left)&set(right)) for index, left in enumerate(candidates.values())
                for right in list(candidates.values())[index+1:]]
    return dict(rosters=len(candidates), unique_players=len(counts),
                common_to_all=sum(v == len(candidates) for v in counts.values()),
                mean_overlap=float(np.mean(overlaps)) if overlaps else None, exposures=dict(counts))


def walk_forward_blend(pool, baseline, reviewed, *, min_date_count=2):
    """Fit one bounded least-squares blend on earlier complete dates only."""
    rows = _usable(pool, ['actual', baseline, reviewed])
    results = []
    for sport, series in rows.groupby('sport'):
        for day, current in series.groupby('date', sort=True):
            earlier = series.loc[series.date.lt(day)]
            if earlier.date.nunique() < min_date_count:
                continue
            delta = earlier[reviewed]-earlier[baseline]
            target = earlier.actual-earlier[baseline]
            # Give each earlier date equal weight, independent of slate size.
            weight = earlier.date.map(1/earlier.date.value_counts())
            denominator = (weight*delta**2).sum()
            if denominator <= 0:
                continue
            blend = float(np.clip((weight*delta*target).sum()/denominator, 0, 1))
            output = current.assign(shadow=current[baseline]+blend*(current[reviewed]-current[baseline]))
            results.append(dict(sport=sport, date=day, earlier_dates=earlier.date.nunique(),
                                earlier_rows=len(earlier), fraction_of_reviewed=blend,
                                comparison=paired_errors(output, [baseline, reviewed, 'shadow'])))
    return results
