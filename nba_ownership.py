"""Compare archived provider ownership with one explicitly identified contest field."""
import pandas as pd


OWNERSHIP_FIELDS = ('ownership_reference_pct', 'ownership_reference_source',
                    'ownership_reference_at_utc', 'ownership_reference_slate')


def archive_ownership(pool, comparison, stamp, source, slate_label):
    """Keep matched reference estimates and their provenance on the saved pool."""
    if comparison.fanduel_id.isna().any() or not comparison.fanduel_id.is_unique:
        raise ValueError('Ownership reference requires unique nonmissing FanDuel IDs.')
    estimates = comparison.set_index('fanduel_id').reference_ownership
    pct = pd.to_numeric(pool.fanduel_id.map(estimates), errors='coerce')
    pct = pct.where(pct.between(0, 100))
    metadata = (source, pd.Timestamp(stamp).tz_convert('UTC').isoformat(), slate_label)
    return pool.assign(ownership_reference_pct=pct, **{
        key: pd.Series(value, index=pool.index).where(pct.notna(), '')
        for key, value in zip(OWNERSHIP_FIELDS[1:], metadata)
    })


def compare_ownership(replay, actual):
    """Validate a reviewed percent-drafted CSV and compare its overlap only."""
    if not set(OWNERSHIP_FIELDS) <= set(replay):
        raise ValueError('This capture has no archived ownership estimates.')
    required = {'fanduel_id', 'field_id', 'actual_ownership_pct', 'source'}
    if actual.empty or not required <= set(actual):
        raise ValueError('Use player IDs, one field ID, ownership percentages and a source.')
    if (not actual.fanduel_id.is_unique or not actual.fanduel_id.isin(replay.fanduel_id).all()
            or actual.field_id.isna().any() or actual.field_id.str.strip().eq('').any()
            or actual.field_id.str.strip().nunique() != 1
            or actual.source.fillna('').str.strip().eq('').any()):
        raise ValueError('Ownership must use unique player IDs from this slate and one identified contest field.')
    actual = actual[list(sorted(required))].copy()
    actual['actual_ownership_pct'] = pd.to_numeric(actual.actual_ownership_pct, errors='coerce')
    if not actual.actual_ownership_pct.between(0, 100).all():
        raise ValueError('Enter actual ownership as a number from 0 to 100.')
    projected = pd.to_numeric(replay.ownership_reference_pct, errors='coerce')
    stamp = pd.to_datetime(replay.ownership_reference_at_utc, utc=True, errors='coerce', format='mixed')
    captured = pd.to_datetime(replay.replay_captured_at_utc, utc=True, errors='coerce', format='mixed')
    valid = (projected.between(0, 100) & stamp.le(captured)
             & replay.ownership_reference_source.fillna('').ne(''))
    matched = replay.loc[valid, ['fanduel_id', 'fanduel_name', *OWNERSHIP_FIELDS]].merge(
        actual, on='fanduel_id', validate='one_to_one')
    if not matched.empty:
        matched['error_pp'] = pd.to_numeric(matched.ownership_reference_pct) - matched.actual_ownership_pct
    return matched


def candidate_ownership_review(pool, rosters, as_of, slate):
    """Compare reference ownership to candidate exposure, not field duplication odds."""
    import numpy as np
    if not set(OWNERSHIP_FIELDS) <= set(pool):
        return pd.DataFrame(), pd.DataFrame()
    if not pool.fanduel_id.is_unique or rosters.empty or not {'lineup','fanduel_id'} <= set(rosters):
        raise ValueError('Use a unique contest pool and candidate rosters.')
    if rosters.lineup.isna().any() or not rosters.fanduel_id.isin(pool.fanduel_id).all():
        raise ValueError('All candidates must match the contest pool.')
    counts = rosters.groupby('lineup').fanduel_id.agg(['size','nunique'])
    if not counts.eq(9).all().all():
        raise ValueError('Each candidate must have nine unique players.')
    now = pd.Timestamp(as_of)
    if now.tzinfo is None or now.tz_convert('America/New_York').date() != slate:
        raise ValueError('Ownership comparison requires the current slate clock.')
    stamps = pd.to_datetime(pool.ownership_reference_at_utc, utc=True, errors='coerce', format='mixed')
    age = (now - stamps).dt.total_seconds() / 3600
    pct = pd.to_numeric(pool.ownership_reference_pct, errors='coerce')
    valid = (pct.between(0,100) & age.between(0,6)
             & stamps.dt.tz_convert('America/New_York').dt.date.eq(slate)
             & pool.ownership_reference_source.fillna('').astype(str).str.strip().ne('')
             & pool.ownership_reference_slate.fillna('').astype(str).str.strip().ne(''))
    references = pool.assign(reference_pct=pct.where(valid))
    # Never combine rows from different provider snapshots.
    covered = references.loc[valid, list(OWNERSHIP_FIELDS[1:])]
    if len(covered.drop_duplicates()) > 1:
        raise ValueError('Use one matched ownership source snapshot at a time.')
    joined = rosters[['lineup','fanduel_id']].merge(
        references[['fanduel_id','fanduel_name','reference_pct','adjusted_fd_points']],
        on='fanduel_id', validate='many_to_one')
    summary = []
    for label, rows in joined.groupby('lineup', sort=False):
        own = rows.reference_pct
        n = int(own.notna().sum())
        summary.append({'Lineup': label, 'Matched ownership players': n,
                        'Mean reference ownership (matched only)': own.mean(),
                        'Total reference ownership (complete only)': own.sum() if n == 9 else np.nan,
                        'Coverage': 'Complete candidate' if n == 9 else 'Partial; do not rank totals'})
    exposure = joined.groupby('fanduel_id').size() * 100 / len(counts)
    players = references.loc[references.fanduel_id.isin(exposure.index),
                             ['fanduel_id','fanduel_name','reference_pct','adjusted_fd_points']].copy()
    players['candidate_exposure_pct'] = players.fanduel_id.map(exposure)
    players['exposure_minus_reference_pp'] = players.candidate_exposure_pct - players.reference_pct
    return pd.DataFrame(summary), players.sort_values(['candidate_exposure_pct','fanduel_id'], ascending=[False,True])



def review_ownership_ceiling(replay, actual):
    """Descriptive calibration on a supplied field; never a leverage score."""
    import numpy as np
    from nba_distribution_review import review_distribution, timestamp
    required = {'fanduel_id','slate_date','eligible','replay_timing',
        'replay_before_full_slate_tip','replay_captured_at_utc','replay_cutoff_utc'} | set(OWNERSHIP_FIELDS)
    if replay.empty or not required <= set(replay) or not replay.fanduel_id.is_unique:
        raise ValueError('Use a verified frozen contest replay for leverage research.')
    ids = replay.fanduel_id.astype(str)
    if not ids.str.fullmatch(r'[0-9]+-[0-9]+').all() or ids.str.split('-').str[0].nunique()!=1:
        raise ValueError('Use one exact contest player pool.')
    if replay.slate_date.nunique()!=1 or replay.slate_date.isna().any():
        raise ValueError('Use one dated slate.')
    day = pd.Timestamp(replay.slate_date.iloc[0]).date()
    capture = pd.to_datetime(replay.replay_captured_at_utc.map(timestamp),utc=True)
    cutoff = pd.to_datetime(replay.replay_cutoff_utc.map(timestamp),utc=True)
    stamps = pd.to_datetime(replay.ownership_reference_at_utc.map(timestamp),utc=True)
    good = (replay.eligible.astype(str).str.lower().eq('true')
        & replay.replay_before_full_slate_tip.astype(str).str.lower().eq('true')
        & replay.replay_timing.eq('before_scheduled_tip')
        & capture.notna() & cutoff.notna() & stamps.notna()
        & capture.lt(cutoff) & stamps.le(capture)
        & stamps.ge(capture-pd.Timedelta(hours=6))
        & stamps.dt.tz_convert('America/New_York').dt.date.eq(day)
        & cutoff.dt.tz_convert('America/New_York').dt.date.eq(day)
        & replay.ownership_reference_slate.fillna('').astype(str).str.strip().ne('')
        & replay.ownership_reference_source.fillna('').astype(str).str.strip().ne('')
        & pd.to_numeric(replay.ownership_reference_pct,errors='coerce').between(0,100))
    valid = replay.loc[good].copy()
    if len(valid.loc[:,list(OWNERSHIP_FIELDS[1:])].drop_duplicates())>1:
        raise ValueError('Use one ownership provider snapshot.')
    matched = compare_ownership(replay,actual)
    matched = matched.loc[matched.fanduel_id.isin(valid.fanduel_id)].copy()
    if matched.empty:
        return matched,pd.DataFrame()
    matched['ownership_reference_pct'] = pd.to_numeric(matched.ownership_reference_pct)
    dist = review_distribution(valid)
    metrics = ['fanduel_id','fd_p85','actual_points','above_p85','p85_pinball','played']
    matched = matched.merge(dist[metrics],on='fanduel_id',how='left',validate='one_to_one')
    matched['ownership_band'] = pd.cut(matched.ownership_reference_pct,
        [-np.inf,10,25,np.inf],right=False,labels=['Under 10%','10–under 25%','25% or more'])
    rows=[]
    for label,group in [('All',matched),*list(matched.groupby('ownership_band',observed=True))]:
        ceiling = group.loc[group.fd_p85.notna() & group.actual_points.notna()]
        rows.append({'Ownership band':str(label),'Matched ownership players':len(group),
            'Mean forecast ownership %':group.ownership_reference_pct.mean(),
            'Mean actual ownership %':group.actual_ownership_pct.mean(),
            'Ownership MAE (pp)':group.error_pp.abs().mean(),
            'Ownership bias (pp)':group.error_pp.mean(),
            'Verified ceiling pairs':len(ceiling),
            'Above provider P85 share':ceiling.above_p85.mean() if len(ceiling) else np.nan,
            'Provider P85 pinball loss':ceiling.p85_pinball.mean() if len(ceiling) else np.nan})
    return matched,pd.DataFrame(rows)
