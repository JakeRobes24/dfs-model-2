"""Freeze exploratory research features and compare fixed shadow forecasts.

No policy here changes a live score, lineup, or learned parameter. Evaluate on
identical eligible played-player samples, excluding unsupported features.
"""
import numpy as np
import pandas as pd

FEATURES = (
    'shadow_recent_fppm', 'shadow_recent_games', 'shadow_recent_minutes',
    'shadow_role_fppm', 'shadow_role_games', 'shadow_role_minutes',
    'shadow_absence_fppm', 'shadow_absence_games', 'shadow_absence_minutes',
    'shadow_absence_teammate', 'shadow_team_pace', 'shadow_matchup_pace',
    'shadow_team_games', 'shadow_opponent_games', 'shadow_opponent_def_rating',
    'shadow_rate_sources', 'shadow_team_sources', 'shadow_opponent_sources',
)
POLICIES = ('Recent rate', 'Confirmed role rate', 'Single OUT teammate rate', 'Pace', 'Recent rate + pace')


def freeze_research_features(pool, summaries, splits, matchup):
    """Attach full-pool pre-slate evidence without modifying reviewed scores."""
    out = pool.copy()
    if not out.fanduel_id.is_unique:
        raise ValueError('Research capture requires unique player IDs.')
    for field in FEATURES:
        out[field] = None
    if not summaries.empty:
        if not summaries.fanduel_id.is_unique:
            raise ValueError('Historical summary requires unique player IDs.')
        s = summaries.set_index('fanduel_id')
        for target, source in {
            'shadow_recent_fppm': 'FD points per minute',
            'shadow_recent_games': 'Games with complete FD stats',
            'shadow_recent_minutes': 'Minutes with complete FD stats',
            'shadow_rate_sources': 'Box-score sources',
        }.items():
            out[target] = out.fanduel_id.map(s[source])
        for role, label in [('starter', 'Starter'), ('bench', 'Bench')]:
            mask = out.prelock_starter.eq(role)
            for target, source in {
                'shadow_role_fppm': 'FD/min as starter' if role == 'starter' else 'FD/min off bench',
                'shadow_role_games': f'{label} complete FD games',
                'shadow_role_minutes': f'{label} complete FD minutes',
            }.items():
                out.loc[mask, target] = out.loc[mask, 'fanduel_id'].map(s[source])
    if not splits.empty:
        # Do not sum effects or select the largest apparent historical gain.
        unique = splits.loc[~splits.fanduel_id.duplicated(keep=False)]
        unique = unique.loc[unique['FD rate evidence'].eq('Observed comparison')].set_index('fanduel_id')
        for target, source in {
            'shadow_absence_fppm': 'FD/min without',
            'shadow_absence_games': 'Complete FD games without',
            'shadow_absence_minutes': 'Complete FD minutes without',
            'shadow_absence_teammate': 'Out teammate',
        }.items():
            out[target] = out.fanduel_id.map(unique[source])
    if not matchup.empty:
        if not matchup.fanduel_id.is_unique:
            raise ValueError('Matchup context requires unique player IDs.')
        m = matchup.set_index('fanduel_id')
        for target, source in {
            'shadow_team_pace': 'team_pace48', 'shadow_matchup_pace': 'descriptive_pace_mean',
            'shadow_team_games': 'team_games', 'shadow_opponent_games': 'opponent_games',
            'shadow_opponent_def_rating': 'opponent_def_rating',
            'shadow_team_sources': 'team_sources', 'shadow_opponent_sources': 'opponent_sources',
        }.items():
            out[target] = out.fanduel_id.map(m[source])
    return out


def compare_shadow_forecasts(replay):
    """Fixed 20% rate shrinkage and capped pace sensitivity; exploratory only.

    Each policy is compared to DAILY and reviewed on exactly its supported rows.
    Missing inputs never become a zero or a fallback forecast.
    """
    if not set(FEATURES) <= set(replay):
        return pd.DataFrame()
    required = {'fanduel_id', 'eligible', 'verified_outcome', 'daily_points',
                'adjusted_fd_points', 'adjusted_minutes', 'actual_points', 'nba_source'}
    if not required <= set(replay) or not replay.fanduel_id.is_unique:
        raise ValueError('Use a verified single frozen replay.')
    frame = replay.loc[replay.eligible.astype(str).str.lower().eq('true')
                       & replay.verified_outcome.eq('played')
                       & replay.nba_source.fillna('').ne('')].copy()
    numeric = lambda name: pd.to_numeric(frame[name], errors='coerce').replace([np.inf, -np.inf], np.nan)
    base, minutes, actual, daily = map(numeric, ['adjusted_fd_points', 'adjusted_minutes', 'actual_points', 'daily_points'])
    usable = base.gt(0) & minutes.gt(0) & minutes.le(60) & actual.notna() & daily.notna()
    candidates = {}
    for policy, prefix in zip(POLICIES[:3], ['recent', 'role', 'absence']):
        rate, games, observed_minutes = (numeric(f'shadow_{prefix}_{field}') for field in ['fppm','games','minutes'])
        support = rate.between(0, 5) & games.ge(3) & observed_minutes.ge(60)
        if prefix == 'absence':
            support &= frame.shadow_absence_teammate.fillna('').ne('')
        candidates[policy] = (base * .8 + minutes * rate * .2).where(support)
    team, match = numeric('shadow_team_pace'), numeric('shadow_matchup_pace')
    support = (team.between(50,150) & match.between(50,150)
               & numeric('shadow_team_games').ge(3) & numeric('shadow_opponent_games').ge(3))
    multiplier = (match / team).clip(.95, 1.05).where(support)
    candidates['Pace'] = base * multiplier
    candidates['Recent rate + pace'] = candidates['Recent rate'] * multiplier
    rows = []
    for policy, predicted in candidates.items():
        mask = usable & predicted.notna()
        n = int(mask.sum())
        baseline_error = (base[mask] - actual[mask]).abs()
        error = (predicted[mask] - actual[mask]).abs()
        rows.append({'Policy': policy, 'Eligible played with baseline': int(usable.sum()),
                     'Paired players': n, 'DAILY MAE': (daily[mask]-actual[mask]).abs().mean(),
                     'Reviewed MAE': baseline_error.mean(), 'Shadow MAE': error.mean(),
                     'MAE improvement vs reviewed': (baseline_error-error).mean(),
                     'Shadow bias': (predicted[mask]-actual[mask]).mean()})
    return pd.DataFrame(rows)
