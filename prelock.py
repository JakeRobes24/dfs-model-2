"""Apply dated, reviewed pre-lock evidence without replacing the contest pool."""
import numpy as np
import pandas as pd

REQUIRED = {'fanduel_id', 'source', 'independent_group', 'observed_at', 'official',
            'status', 'starter', 'role', 'minutes'}
OFFICIAL_OUT = {'out', 'inactive', 'suspended'}
OFFICIAL_STATUS = OFFICIAL_OUT | {'available', 'probable', 'questionable', 'doubtful'}
STARTING_STATUS = {'starter', 'bench'}


def review_prelock_evidence(pool, evidence, as_of, max_age_hours=6):
    """Normalize and audit evidence once, before any projection adjustment."""
    missing = REQUIRED - set(evidence.columns)
    if missing:
        raise ValueError(f'Pre-lock evidence missing columns: {sorted(missing)}')
    if pool.fanduel_id.isna().any() or pool.fanduel_id.duplicated().any():
        raise ValueError('Contest pool must contain unique FanDuel IDs')
    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        raise ValueError('Enter an as-of timestamp with a UTC offset')
    if not np.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError('Evidence age must be positive')

    notes = evidence.copy()
    dated = notes.observed_at.astype('string').fillna('').astype(str).str.strip()
    has_offset = dated.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$', regex=True)
    notes['observed_at'] = pd.to_datetime(dated.where(has_offset), utc=True, errors='coerce', format='mixed')
    notes['source'] = notes.source.astype('string').fillna('').astype(str).str.strip()
    notes['independent_group'] = notes.independent_group.astype('string').fillna('').astype(str).str.strip().str.casefold()
    notes['official'] = notes.official.astype('string').fillna('').astype(str).str.casefold().isin({'true', '1'})
    for col in ('status', 'starter', 'role'):
        notes[col] = notes[col].astype('string').fillna('').astype(str).str.strip()
    notes['minutes'] = pd.to_numeric(notes.minutes, errors='coerce').where(lambda x: x.between(0, 48))
    notes['review'] = np.select(
        [~notes.fanduel_id.isin(pool.fanduel_id), notes.source.eq(''), notes.observed_at.isna(),
         notes.observed_at.gt(cutoff), notes.observed_at.lt(cutoff - pd.Timedelta(hours=max_age_hours))],
        ['Unknown contest ID', 'Missing source', 'Missing/invalid timestamp', 'After as-of time', 'Stale'],
        default='Reviewed',
    )
    return notes


def apply_prelock(pool, evidence, as_of, max_age_hours=6):
    notes = review_prelock_evidence(pool, evidence, as_of, max_age_hours)
    result = pool.copy()
    result['prelock_prior_fd_points'] = result.adjusted_fd_points
    result['prelock_change'] = ''
    result['prelock_status'] = ''
    result['prelock_starter'] = ''
    result['prelock_role'] = ''
    result['prelock_sources'] = ''
    reviewed = notes.loc[notes.review.eq('Reviewed')].sort_values('observed_at')
    by_id = dict(tuple(reviewed.groupby('fanduel_id')))
    for idx, player in result.iterrows():
        entries = by_id.get(player.fanduel_id)
        if entries is None:
            continue
        result.at[idx, 'prelock_sources'] = ' | '.join(dict.fromkeys(entries.source))
        labels = []
        official = entries[entries.official]
        for column, values in [('status', OFFICIAL_STATUS), ('starter', STARTING_STATUS)]:
            decisions = official[official[column].str.casefold().isin(values)]
            if decisions.empty:
                continue
            latest = decisions[decisions.observed_at.eq(decisions.observed_at.max())]
            distinct = latest[column].str.casefold().unique()
            if len(distinct) == 1:
                result.at[idx, 'prelock_' + column] = distinct[0]
                labels.append(f'{column}: {distinct[0]}')
            else:
                labels.append(f'Conflicting official {column}')
                if column == 'status' and any(value in OFFICIAL_OUT for value in distinct):
                    result.at[idx, 'eligible'] = False

        roles = entries.loc[entries.role.ne(''), 'role'].unique()
        if len(roles) == 1:
            result.at[idx, 'prelock_role'] = roles[0]
            labels.append('role: ' + roles[0])
        elif len(roles) > 1:
            labels.append('Conflicting roles')
        if result.at[idx, 'prelock_status'] in OFFICIAL_OUT:
            result.at[idx, 'eligible'] = False
            result.at[idx, 'adjusted_minutes'] = 0.0
            if pd.notna(player.adjusted_fd_points):
                result.at[idx, 'adjusted_fd_points'] = 0.0
            result.at[idx, 'minutes_method'] = 'official_out'
            result.at[idx, 'confidence'] = 'excluded'
        # A fresh official available decision may correct a stale contest OUT.
        # Restore the original forecast, never the zeroed OUT projection.
        if (result.at[idx, 'prelock_status'] == 'available'
                and str(player.get('injury_flag', '')).upper() in {'O', 'OUT'}
                and player.get('minutes_method') == 'contest_out'):
            result.at[idx, 'eligible'] = True
            baseline = pd.to_numeric(player.get('projected_minutes'), errors='coerce')
            rate = pd.to_numeric(player.get('fppm'), errors='coerce')
            usable = pd.notna(baseline) and np.isfinite(baseline) and 0 < baseline <= 48
            result.at[idx, 'adjusted_minutes'] = float(baseline) if usable else np.nan
            result.at[idx, 'adjusted_fd_points'] = (float(rate) * baseline
                if usable and pd.notna(rate) and np.isfinite(rate) and rate >= 0 else np.nan)
            result.at[idx, 'minutes_method'] = 'official_available_baseline'
            result.at[idx, 'confidence'] = 'low' if usable else 'missing'
            labels.append('Official available supersedes contest OUT; reassess role/minutes')
        if result.at[idx, 'eligible']:
            estimates = entries[entries.minutes.notna() & entries.independent_group.ne('')]
            # Estimates predating a reviewed official role/status change
            # cannot confirm the player's current minutes.
            changes = official.loc[official.status.str.casefold().isin(OFFICIAL_STATUS)
                                   | official.starter.str.casefold().isin(STARTING_STATUS)]
            if not changes.empty:
                estimates = estimates.loc[estimates.observed_at.ge(changes.observed_at.max())]
            latest = estimates.loc[estimates.observed_at.eq(
                estimates.groupby('independent_group').observed_at.transform('max'))]
            conflict = latest.groupby('independent_group').minutes.nunique().gt(1).any()
            latest = latest.drop_duplicates('independent_group', keep='last')
            if not conflict and len(latest) >= 2 and latest.minutes.max() - latest.minutes.min() <= 4:
                minutes = float(latest.minutes.median())
                result.at[idx, 'adjusted_minutes'] = minutes
                if pd.notna(player.fppm):
                    result.at[idx, 'adjusted_fd_points'] = float(player.fppm) * minutes
                result.at[idx, 'minutes_method'] = 'prelock_independent_consensus'
                result.at[idx, 'confidence'] = 'medium'
                if pd.isna(player.adjusted_minutes) or abs(minutes - player.adjusted_minutes) >= 2:
                    labels.append('Verified minutes changed')
            elif len(estimates):
                labels.append('Minutes estimates need corroboration')
        result.at[idx, 'prelock_change'] = ' | '.join(labels)
    return result, notes
