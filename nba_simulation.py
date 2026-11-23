"""Experimental NBA outcome ranges conditional on a player taking the court."""
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd


MINUTE_BANDS = (18, 28)
MIN_COHORT = 20
QUANTILES = (.1, .5, .9)


def _numeric(frame, columns):
    return frame[list(columns)].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)


def _history_rows(history):
    fields = ['daily_minutes', 'daily_points', 'actual_minutes', 'actual_points']
    numeric = _numeric(history, fields)
    unique = ~history.duplicated(['slate_date', 'fanduel_id'], keep=False)
    valid = (unique & history.fanduel_id.notna() & history.eligible.eq(True)
             & numeric.daily_minutes.gt(0) & numeric.daily_minutes.le(48)
             & numeric.daily_points.gt(0) & numeric.actual_minutes.gt(0)
             & numeric.actual_minutes.le(60) & numeric.actual_points.notna())
    rows = numeric.loc[valid].copy()
    rows.insert(0, 'fanduel_id', history.loc[valid, 'fanduel_id'])
    rows.insert(0, 'slate_date', history.loc[valid, 'slate_date'])
    return rows


@dataclass
class OutcomeDraws:
    fanduel_ids: pd.Index
    minutes: np.ndarray
    fd_points: np.ndarray

    def player_ranges(self):
        result = {'fanduel_id': self.fanduel_ids}
        for metric, draws in [('minutes', self.minutes), ('fd', self.fd_points)]:
            for pct, values in zip((10, 50, 90), np.quantile(draws, QUANTILES, axis=0)):
                result[f'{metric}_p{pct}'] = values
        return pd.DataFrame(result)

    def _lineup_totals(self, rosters):
        totals = {}
        for lineup, roster in rosters.groupby('lineup', sort=False):
            if len(roster) != 9 or not roster.fanduel_id.is_unique:
                raise ValueError('Each simulation roster needs nine distinct players.')
            indices = self.fanduel_ids.get_indexer(roster.fanduel_id)
            if (indices < 0).any():
                raise ValueError('A lineup player has no simulated outcomes.')
            totals[lineup] = self.fd_points[:, np.sort(indices)].sum(axis=1)
        return totals

    def lineup_ranges(self, rosters):
        """Summarize approved optimizer rosters using shared player draws."""
        rows = []
        for lineup, totals in self._lineup_totals(rosters).items():
            p10, median, p90 = np.quantile(totals, QUANTILES)
            rows.append({'lineup': lineup, 'fd_p10': p10, 'fd_p50': median, 'fd_p90': p90,
                         'fd_stddev': totals.std()})
        return pd.DataFrame(rows)

    def compare_lineups(self, rosters):
        """Compare pairs of supplied rosters on the same simulated outcomes."""
        rows = []
        for (left, first), (right, second) in combinations(self._lineup_totals(rosters).items(), 2):
            gaps = first - second
            tie = np.isclose(gaps, 0, atol=1e-9)
            p10, p50, p90 = np.quantile(gaps, QUANTILES)
            rows.append({
                'lineup': left, 'alternative': right, 'draws': len(gaps),
                'lineup_ahead_share': np.mean((gaps > 0) & ~tie),
                'tie_share': np.mean(tie),
                'alternative_ahead_share': np.mean((gaps < 0) & ~tie),
                'fd_gap_p10': p10, 'fd_gap_p50': p50, 'fd_gap_p90': p90,
            })
        return pd.DataFrame(rows)


def simulate_nba(history, pool, slate_date, *, draws=4000, seed=42, center_on_projection=True):
    """Sample paired minutes and efficiency errors from earlier completed games.

    By default, center residuals on the supplied projections. Role bands use
    projected minutes. Fall back to all training rows for sparse bands.
    Outcomes are independent across players until game correlations can be
    validated. Scores are conditional on playing; DNP risk is outside this model.
    Disable centering only to compare a historical-bias correction in research.
    """
    if not isinstance(draws, int) or not 1 <= draws <= 20000:
        raise ValueError('Use between 1 and 20,000 simulation draws.')
    prior = history.copy()
    prior['slate_date'] = pd.to_datetime(prior.slate_date, errors='coerce').dt.normalize()
    prior = _history_rows(prior.loc[prior.slate_date.lt(pd.Timestamp(slate_date).normalize())])
    prior = prior.sort_values(['slate_date', 'fanduel_id'])
    if len(prior) < MIN_COHORT:
        raise ValueError('Insufficient earlier, verified played outcomes for simulated ranges.')
    target = _numeric(pool, ['projected_minutes', 'projected_fd_points'])
    if (target.empty or not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any()
            or not target.projected_minutes.gt(0).all()
            or not target.projected_minutes.le(48).all()
            or not target.projected_fd_points.gt(0).all()):
        raise ValueError('Simulation requires unique players and valid positive projections.')

    base_minutes = target.projected_minutes.to_numpy()
    rate = target.projected_fd_points.to_numpy() / base_minutes
    historic_rate = prior.daily_points / prior.daily_minutes
    errors = np.column_stack((prior.actual_minutes - prior.daily_minutes,
                              prior.actual_points - prior.actual_minutes * historic_rate))
    if not np.isfinite(errors).all() or not np.isfinite(rate).all():
        raise ValueError('Simulation inputs produced non-finite point rates.')
    train_bands = np.digitize(prior.daily_minutes, MINUTE_BANDS)
    target_bands = np.digitize(base_minutes, MINUTE_BANDS)
    rng = np.random.default_rng(seed)
    minutes = np.empty((draws, len(target)))
    points = np.empty_like(minutes)
    for band in np.unique(target_bands):
        group = errors[train_bands == band]
        if len(group) < MIN_COHORT:
            group = errors
        chosen = target_bands == band
        if center_on_projection:
            group = group - group.mean(axis=0)
        sampled = group[rng.integers(len(group), size=(draws, chosen.sum()))]
        minutes[:, chosen] = np.clip(base_minutes[chosen] + sampled[:, :, 0], 1 / 60, 60)
        points[:, chosen] = minutes[:, chosen] * rate[chosen] + sampled[:, :, 1]
    return OutcomeDraws(pd.Index(pool.fanduel_id), minutes, points)


def walk_forward_ranges(history, *, draws=4000, seed=42, center_on_projection=True):
    """Score held-out player ranges with strictly earlier dates as training."""
    normalized = history.copy()
    normalized['slate_date'] = pd.to_datetime(normalized.slate_date, errors='coerce').dt.normalize()
    evaluated = _history_rows(normalized.dropna(subset=['slate_date']))
    reports = []
    for day, heldout in evaluated.groupby('slate_date', sort=True):
        training = evaluated.loc[evaluated.slate_date.lt(day)]
        if len(training) < MIN_COHORT:
            continue
        pool = heldout.rename(columns={'daily_minutes': 'projected_minutes',
                                       'daily_points': 'projected_fd_points'})
        simulated = simulate_nba(normalized, pool, day, draws=draws, seed=seed,
                                 center_on_projection=center_on_projection).player_ranges()
        paired = heldout.merge(simulated, on='fanduel_id', validate='one_to_one')
        report = {'slate_date': day.date().isoformat(), 'training_players': len(training),
                  'test_players': len(paired)}
        for metric, actual in [('minutes', 'actual_minutes'), ('fd', 'actual_points')]:
            low, middle, high = (paired[f'{metric}_p{pct}'] for pct in (10, 50, 90))
            outcomes = paired[actual]
            report[f'{metric}_80pct_coverage'] = outcomes.between(low, high).mean()
            report[f'{metric}_below_range'] = outcomes.lt(low).mean()
            report[f'{metric}_above_range'] = outcomes.gt(high).mean()
            report[f'{metric}_mean_width'] = (high - low).mean()
            report[f'{metric}_median_mae'] = (middle - outcomes).abs().mean()
            baseline = 'daily_minutes' if metric == 'minutes' else 'daily_points'
            report[f'{metric}_daily_mae'] = (paired[baseline] - outcomes).abs().mean()
        reports.append(report)
    return pd.DataFrame(reports)
