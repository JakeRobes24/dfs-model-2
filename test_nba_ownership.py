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


def test_candidate_exposure_reference_review_keeps_missing_and_stale_unknown():
    from datetime import date
    from nba_ownership import candidate_ownership_review
    ids = [f'143-{i}' for i in range(10)]
    pool = pd.DataFrame({'fanduel_id': ids, 'fanduel_name': ids, 'adjusted_fd_points': 30})
    provider = pd.DataFrame({'fanduel_id': ids[:9], 'reference_ownership': [0]+[20]*8})
    frozen = archive_ownership(pool, provider, '2026-11-24T22:00:00Z', 'FTA board', 'Main')
    rosters = pd.DataFrame({'lineup': ['A']*9+['B']*9, 'fanduel_id': ids[:9]+ids[1:]})
    report, players = candidate_ownership_review(frozen, rosters, '2026-11-24T23:00:00Z', date(2026,11,24))
    report = report.set_index('Lineup')
    players = players.set_index('fanduel_id')
    assert report.loc['A','Matched ownership players'] == 9
    assert report.loc['A','Total reference ownership (complete only)'] == 160
    assert report.loc['B','Matched ownership players'] == 8
    assert pd.isna(report.loc['B','Total reference ownership (complete only)'])
    assert players.loc[ids[0],'candidate_exposure_pct'] == 50
    assert players.loc[ids[0],'exposure_minus_reference_pp'] == 50
    assert pd.isna(players.loc[ids[-1],'exposure_minus_reference_pp'])
    stale,_ = candidate_ownership_review(frozen, rosters, '2026-11-25T04:30:00Z', date(2026,11,24))
    assert stale['Matched ownership players'].eq(0).all()
    mixed = frozen.copy()
    mixed.loc[0,'ownership_reference_source'] = 'Other provider'
    with pytest.raises(ValueError, match='one matched ownership'):
        candidate_ownership_review(mixed, rosters, '2026-11-24T23:00:00Z', date(2026,11,24))
