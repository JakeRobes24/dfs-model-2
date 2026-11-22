"""Compare archived provider ownership with one explicitly identified contest field."""
import pandas as pd


OWNERSHIP_FIELDS = ('ownership_reference_pct', 'ownership_reference_source',
                    'ownership_reference_at_utc', 'ownership_reference_slate')


def archive_ownership(pool, comparison, stamp, source, slate_label):
    """Keep matched reference estimates and their provenance on the saved pool."""
    estimates = comparison.set_index('fanduel_id', verify_integrity=True).reference_ownership
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
