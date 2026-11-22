import pandas as pd
import pytest

from nba_ownership import archive_ownership, compare_ownership


def test_archived_ownership_preserves_unknowns_and_matches_only_frozen_overlap():
    pool = pd.DataFrame({'fanduel_id': ['143-1', '143-2', '143-3'], 'fanduel_name': ['A', 'B', 'C'],
                         'replay_captured_at_utc': '2026-11-22T23:00:00Z'})
    provider = pd.DataFrame({'fanduel_id': ['143-1', '143-2'], 'reference_ownership': [0, 38]})
    frozen = archive_ownership(pool, provider, '2026-11-22T22:00:00Z', 'FTA board', 'Main')
    assert pd.isna(frozen.loc[2, 'ownership_reference_pct'])
    assert frozen.loc[2, 'ownership_reference_source'] == ''
    frozen.loc[1, 'ownership_reference_at_utc'] = '2026-11-22T23:30:00Z'
    actual = pd.DataFrame({'fanduel_id': pool.fanduel_id, 'field_id': 'field-100',
                           'source': 'Reviewed standings', 'actual_ownership_pct': [4, 30, 10]})
    matched = compare_ownership(frozen, actual)
    assert matched.fanduel_id.tolist() == ['143-1']
    assert matched.error_pp.tolist() == [-4]
    with pytest.raises(ValueError, match='one identified contest field'):
        compare_ownership(frozen, actual.assign(field_id=['field-100', 'field-200', 'field-100']))
    with pytest.raises(ValueError, match='unique player IDs'):
        compare_ownership(frozen, actual.assign(fanduel_id=['143-1', '144-2', '143-3']))
    with pytest.raises(ValueError, match='number from 0 to 100'):
        compare_ownership(frozen, actual.assign(actual_ownership_pct=-5))
