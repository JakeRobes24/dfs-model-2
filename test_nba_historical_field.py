import pandas as pd
import pytest

from model import SLOTS
from nba_historical_field import review_supplied_field


def fixture():
    ids = [f'143-{i}' for i in range(10)]
    pool = pd.DataFrame({'fanduel_id': ids, 'salary': '6000',
                         'roster_eligibility': 'PG/SG/SF/PF/C/G/F/F/C/UTIL',
                         'team': ['BOS']*3 + ['NYK']*3 + ['CLE']*4})
    a, b = ids[:9], ids[1:]
    candidates = pd.DataFrame({'lineup': ['A']*9 + ['B']*9,
                               'slot': SLOTS*2, 'fanduel_id': a+b})
    field = pd.DataFrame({'field_id': 'field-1', 'source': 'Reviewed anonymous entries',
                          'entry_id': ['entry1']*9+['entry2']*9+['entry3']*9,
                          'slot': SLOTS*3, 'fanduel_id': a+a+b})
    results = pd.DataFrame({'fanduel_id': ids, 'outcome': 'Played',
                            'nba_fd_points': [20]+[30]*8+[40], 'nba_source': 'NBA final box'})
    return pool,candidates,field,results


def test_supplied_field_scores_duplicate_rosters_and_sample_exposure():
    pool,candidates,field,results = fixture()
    report, exposure = review_supplied_field(pool,candidates,field,results)
    report = report.set_index('Lineup')
    assert report.loc['A','Official box-score FD'] == 260
    assert report.loc['A','Entries tied'] == 2
    assert report.loc['A','Entries scoring higher'] == 1
    assert report.loc['A','Identical supplied rosters'] == 2
    assert report.loc['A','Sample midrank percentile'] == pytest.approx(100/3)
    assert report.loc['B','Official box-score FD'] == 280
    assert report.loc['B','Entries scoring lower'] == 2
    assert report.loc['B','Sample midrank percentile'] == pytest.approx(250/3)
    assert exposure.sample_ownership_pct.sum() == pytest.approx(900)
    assert exposure.iloc[0].sample_ownership_pct == pytest.approx(200/3)


def test_supplied_field_requires_complete_official_results_and_legal_entries():
    pool,candidates,field,results = fixture()
    for invalid in [field.iloc[:-1], field.assign(field_id=['other']+['field-1']*26),
                    field.assign(fanduel_id=['other']+field.fanduel_id.iloc[1:].tolist()),
                    field.assign(slot=['UTIL']+field.slot.iloc[1:].tolist())]:
        with pytest.raises(ValueError):
            review_supplied_field(pool,candidates,invalid,results)
    for invalid in [pool.assign(salary=7000), pool.assign(team='BOS')]:
        with pytest.raises(ValueError, match='violates'):
            review_supplied_field(invalid,candidates,field,results)
    with pytest.raises(ValueError, match='unresolved'):
        review_supplied_field(pool,candidates,field,results.assign(nba_source=''))
    results.loc[0,'outcome'] = 'Did not play'
    results.loc[0,'nba_fd_points'] = None
    report,_ = review_supplied_field(pool,candidates,field,results)
    assert report.loc[0,'Official box-score FD'] == 240
