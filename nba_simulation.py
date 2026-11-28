"""Experimental NBA outcome ranges conditional on a player taking the court."""
from dataclasses import dataclass
from itertools import combinations
import json

import numpy as np
import pandas as pd


MINUTE_BANDS = (18, 28)
MIN_COHORT = 20
QUANTILES = (.1, .5, .9)


def candidate_range_receipt(pool, rosters, ranges, *, slate, captured_at, timing,
                            draws, seed, training_players):
    """Export the exact player forecasts and candidate ranges displayed in the audit."""
    when = pd.Timestamp(captured_at)
    timings = {'before_scheduled_tip', 'at_or_after_cutoff', 'schedule_unverified'}
    if (pd.isna(when) or when.tzinfo is None or timing not in timings
            or (timing=='before_scheduled_tip' and when.tz_convert('America/New_York').date()!=slate)):
        raise ValueError('Invalid simulation capture timestamp or timing.')
    if type(draws) is not int or draws < 1 or type(seed) is not int or type(training_players) is not int or training_players < 1:
        raise ValueError('Simulation receipt requires its draw, seed and training settings.')
    roster_columns = ['lineup', 'fanduel_id']
    point_columns = ['adjusted_minutes','adjusted_fd_points']
    ranges_columns = ['lineup','reviewed_fd','fd_p10','fd_p50','fd_p90','fd_stddev']
    players = rosters[roster_columns].merge(pool[['fanduel_id', *point_columns]], on='fanduel_id',
                                           how='left',validate='many_to_one')
    ids = players.fanduel_id
    if (players.empty or not ids.str.fullmatch(r'\d+-\d+').all()
            or ids.str.split('-').str[0].nunique()!=1
            or players.lineup.isna().any() or players.duplicated(roster_columns).any()
            or not players.groupby('lineup').size().eq(9).all()):
        raise ValueError('Simulation receipt requires nine distinct players per candidate in one contest.')
    scores = ranges[ranges_columns]
    if scores.lineup.isna().any() or not scores.lineup.is_unique or set(scores.lineup)!=set(players.lineup):
        raise ValueError('Candidate ranges do not match the archived rosters.')
    projections = _numeric(players, point_columns)
    numeric = _numeric(scores, ranges_columns[1:])
    if (not projections.notna().all().all() or not projections.gt(0).all().all()
            or not numeric.notna().all().all() or not numeric.fd_stddev.ge(0).all()
            or not (numeric.fd_p10.le(numeric.fd_p50)&numeric.fd_p50.le(numeric.fd_p90)).all()):
        raise ValueError('Simulation receipt requires valid projections and ordered quantiles.')
    expected = projections.adjusted_fd_points.groupby(players.lineup).sum()
    if not np.allclose(scores.lineup.map(expected), numeric.reviewed_fd, atol=1e-8, rtol=0):
        raise ValueError('Candidate projected totals disagree with the displayed inputs.')
    return json.dumps(dict(schema=1, contest=ids.iloc[0].split('-')[0], slate_date=slate.isoformat(),
                           captured_at_utc=when.tz_convert('UTC').isoformat(), timing=timing,
                           method='reviewed_minutes_independent_played_residuals', conditional_on_playing=True,
                           draws=draws, seed=seed, training_players=training_players,
                           players=players.assign(**projections).to_dict('records'),
                           ranges=scores.assign(**numeric).to_dict('records')),
                      indent=2, allow_nan=False)+'\n'


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

    def review_lineup_comparisons(self, rosters, projections, official_results):
        """Audit the played-only model against complete, verified historical pairs."""
        pairs = self.compare_lineups(rosters)
        if pairs.empty:
            return pairs
        played = official_results.loc[official_results.outcome.eq('Played')
                                      & official_results.nba_source.fillna('').ne('')]
        players = rosters[['lineup', 'fanduel_id']].merge(
            projections[['fanduel_id', 'projected_fd_points']], on='fanduel_id', how='left', validate='many_to_one',
        ).merge(played[['fanduel_id', 'nba_fd_points']], on='fanduel_id', how='left', validate='many_to_one')
        fields = ['projected_fd_points', 'nba_fd_points']
        totals = _numeric(players, fields).groupby(players.lineup).sum(min_count=9)
        for field, name in zip(fields, ('projected_gap', 'actual_gap')):
            pairs[name] = pairs.lineup.map(totals[field]) - pairs.alternative.map(totals[field])
        reviewed = pairs.dropna(subset=['projected_gap', 'actual_gap']).copy()
        reviewed['actual_gap'] = reviewed.actual_gap.round(1)
        reviewed['actual_result'] = np.sign(reviewed.actual_gap)
        reviewed['projection_direction_correct'] = np.sign(reviewed.projected_gap.round(2)).eq(reviewed.actual_result)
        direction = reviewed.lineup_ahead_share - reviewed.alternative_ahead_share
        reviewed['simulation_direction_correct'] = np.sign(direction).eq(reviewed.actual_result)
        probability = reviewed.lineup_ahead_share + reviewed.tie_share / 2
        actual = reviewed.actual_result.gt(0).where(reviewed.actual_result.ne(0))
        reviewed['simulation_brier'] = (probability - actual) ** 2
        return reviewed


def simulate_nba(history, pool, slate_date, *, draws=4000, seed=42, center_on_projection=True,
                 rate_scaled=False):
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
    if rate_scaled:
        prior = prior.loc[prior.actual_minutes.ge(10)]
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
    production_error = prior.actual_points - prior.actual_minutes * historic_rate
    if rate_scaled:
        production_error = production_error / prior.actual_minutes
    errors = np.column_stack((prior.actual_minutes - prior.daily_minutes, production_error))
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
        residual = sampled[:, :, 1] * minutes[:, chosen] if rate_scaled else sampled[:, :, 1]
        points[:, chosen] = minutes[:, chosen] * rate[chosen] + residual
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


def simulate_reviewed_candidates(history, scored_pool, rosters, slate_date, *, draws=4000, seed=42, return_draws=False):
    """Informational lineup comparison centered on reviewed, rather than DAILY, scores.

    Use earlier verified played rows from frozen pre-tip replay exports. DAILY
    residuals applied to reviewed means are experimental, not an optimizer objective.
    """
    required = {'slate_date', 'fanduel_id', 'eligible', 'daily_minutes', 'daily_points',
                'actual_minutes', 'actual_points', 'verified_outcome', 'nba_source',
                'replay_before_full_slate_tip', 'replay_captured_at_utc', 'replay_cutoff_utc'}
    if not required <= set(history):
        raise ValueError('Use verified frozen player_replay.csv exports, not generic history or actuals.')
    history = history.reset_index(drop=True).copy()
    captured = pd.to_datetime(history.replay_captured_at_utc, utc=True, errors='coerce', format='mixed')
    cutoff = pd.to_datetime(history.replay_cutoff_utc, utc=True, errors='coerce', format='mixed')
    day = pd.to_datetime(history.slate_date, errors='coerce').dt.normalize()
    verified = (history.verified_outcome.eq('played')
                & history.nba_source.fillna('').astype(str).str.strip().ne('')
                & history.replay_before_full_slate_tip.astype(str).str.lower().eq('true')
                & captured.lt(cutoff) & cutoff.dt.tz_convert('America/New_York').dt.date.eq(day.dt.date)
                & day.lt(pd.Timestamp(slate_date).normalize()))
    history['eligible'] = history.eligible.astype(str).str.lower().eq('true')
    history['slate_date'] = day
    history = history.loc[verified].copy()
    fields = {'fanduel_id', 'eligible', 'adjusted_minutes', 'adjusted_fd_points'}
    if not fields <= set(scored_pool) or not scored_pool.fanduel_id.is_unique:
        raise ValueError('Simulation requires the unique reviewed contest pool.')
    if not {'lineup', 'fanduel_id'} <= set(rosters) or rosters.empty:
        raise ValueError('Generate legal candidates before running the comparison.')
    selected = scored_pool.loc[scored_pool.fanduel_id.isin(rosters.fanduel_id)].copy()
    if (set(selected.fanduel_id) != set(rosters.fanduel_id)
            or not selected.eligible.eq(True).all()):
        raise ValueError('Candidate simulation requires every player to remain eligible in the reviewed pool.')
    target = selected[['fanduel_id', 'adjusted_minutes', 'adjusted_fd_points']].rename(columns={
        'adjusted_minutes': 'projected_minutes', 'adjusted_fd_points': 'projected_fd_points',
    }).sort_values('fanduel_id')
    outcomes = simulate_nba(history, target, slate_date, draws=draws, seed=seed)
    ranges = outcomes.lineup_ranges(rosters)
    points = target.set_index('fanduel_id').projected_fd_points
    totals = rosters.assign(reviewed_fd=rosters.fanduel_id.map(points)).groupby('lineup').reviewed_fd.sum()
    ranges.insert(1, 'reviewed_fd', ranges.lineup.map(totals))
    result = (ranges, outcomes.compare_lineups(rosters), len(_history_rows(history)))
    return (*result, outcomes) if return_draws else result


def compare_residual_training(history, target_day, *, draws=4000, seed=42, rate_scale_comparison=False):
    """Walk-forward comparison of DAILY vs reviewed residual distributions.

    Train both on the same verified played rows from one complete pre-tip
    capture per date. Hold the later reviewed forecast constant. The optional
    rate-scale comparison uses reviewed errors and identical ten-minute minimum
    training rows for both policies. It is separate from lineup simulation.
    """
    fields={'slate_date','fanduel_id','eligible','daily_minutes','daily_points',
            'adjusted_minutes','adjusted_fd_points','actual_minutes','actual_points',
            'verified_outcome','nba_source','replay_before_full_slate_tip',
            'replay_captured_at_utc','replay_cutoff_utc','replay_timing'}
    if not fields <= set(history):
        return pd.DataFrame(),pd.DataFrame()
    data=history.copy()
    data['slate_date']=pd.to_datetime(data.slate_date,errors='coerce').dt.normalize()
    data=data.loc[data.slate_date.lt(pd.Timestamp(target_day).normalize())]
    verified=[]
    for day,frame in data.groupby('slate_date',sort=True):
        ids=frame.fanduel_id.astype(str)
        captured=pd.to_datetime(frame.replay_captured_at_utc,utc=True,errors='coerce',format='mixed')
        cutoff=pd.to_datetime(frame.replay_cutoff_utc,utc=True,errors='coerce',format='mixed')
        if (not ids.is_unique or not ids.str.fullmatch(r'[0-9]{1,12}-[0-9]+').all()
            or ids.str.split('-').str[0].nunique()!=1 or captured.nunique()!=1
            or not captured.lt(cutoff).all()
            or not cutoff.dt.tz_convert('America/New_York').dt.date.eq(day.date()).all()
            or not frame.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()
            or not frame.replay_timing.eq('before_scheduled_tip').all()):
            continue
        frame=frame.copy()
        frame['eligible']=frame.eligible.astype(str).str.lower().eq('true')
        nums=['daily_minutes','daily_points','adjusted_minutes','adjusted_fd_points',
              'actual_minutes','actual_points']
        frame[nums]=_numeric(frame,nums)
        mask=(frame.eligible & frame.verified_outcome.eq('played')
              & frame.nba_source.fillna('').astype(str).str.strip().ne('')
              & frame.daily_minutes.between(1/60,48) & frame.adjusted_minutes.between(1/60,48)
              & frame.daily_points.gt(0) & frame.adjusted_fd_points.gt(0)
              & frame.actual_minutes.between(1/60,60) & frame.actual_points.notna())
        verified.append(frame.loc[mask])
    if not verified:
        return pd.DataFrame(),pd.DataFrame()
    data=pd.concat(verified,ignore_index=True)
    reports=[]
    for day,held in data.groupby('slate_date',sort=True):
        prior=data.loc[data.slate_date.lt(day)]
        if rate_scale_comparison:
            prior = prior.loc[prior.actual_minutes.ge(10)]
        if len(prior)<MIN_COHORT:
            continue
        target=held[['fanduel_id','adjusted_minutes','adjusted_fd_points']].rename(
            columns={'adjusted_minutes':'projected_minutes','adjusted_fd_points':'projected_fd_points'})
        revised=prior.assign(daily_minutes=prior.adjusted_minutes,daily_points=prior.adjusted_fd_points)
        policies = [('DAILY residuals', prior, False), ('Reviewed residuals', revised, False)]
        if rate_scale_comparison:
            policies = [('Reviewed point errors', revised, False), ('Reviewed rate errors', revised, True)]
        for policy, train, rate_scaled in policies:
            ranges=simulate_nba(train,target,day,draws=draws,seed=seed,rate_scaled=rate_scaled).player_ranges()
            paired=held.merge(ranges,on='fanduel_id',validate='one_to_one')
            for metric in ('fd','minutes'):
                actual=paired.actual_points if metric=='fd' else paired.actual_minutes
                lo,mid,hi=(paired[f'{metric}_p{p}'] for p in (10,50,90))
                # Proper central 80% interval score penalizes excessive width
                # as well as misses, so maximizing coverage alone cannot win.
                interval=(hi-lo)+10*(lo-actual).clip(lower=0)+10*(actual-hi).clip(lower=0)
                reports.append(dict(slate_date=day.date().isoformat(),policy=policy,metric=metric,
                    train_players=len(prior),test_players=len(paired),
                    coverage=actual.between(lo,hi).mean(),width=(hi-lo).mean(),
                    interval_score=interval.mean(),median_mae=(mid-actual).abs().mean(),
                    above_p90=actual.gt(hi).mean(),below_p10=actual.lt(lo).mean()))
    daily=pd.DataFrame(reports)
    if daily.empty:
        return daily,pd.DataFrame()
    summary=daily.groupby(['policy','metric'],as_index=False).agg(
        dates=('slate_date','nunique'),paired_players=('test_players','sum'),
        equal_date_interval_score=('interval_score','mean'),
        equal_date_coverage=('coverage','mean'),equal_date_width=('width','mean'),
        equal_date_median_mae=('median_mae','mean'),
        equal_date_above_p90=('above_p90','mean'))
    summary['status']='Experimental; no automatic promotion'
    return daily,summary
