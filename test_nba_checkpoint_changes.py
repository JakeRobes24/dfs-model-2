import pandas as pd
import pytest
from nba_checkpoint_changes import compare_checkpoints


def test_checkpoint_detects_all_player_changes_and_ignores_metadata():
    pool = pd.DataFrame([
        dict(fanduel_id='100-1', fanduel_name='Alpha', team='BOS',game='BOS@NYK',
             salary=5000,roster_eligibility='PG',eligible=True,prelock_status='',
             prelock_starter='',prelock_role='Projected starter',confidence='medium',
             adjusted_minutes=30,adjusted_fd_points=32.0,projection_scored_at_utc='old'),
        dict(fanduel_id='100-2', fanduel_name='Beta', team='NYK',game='BOS@NYK',
             salary=4000,roster_eligibility='C',eligible=True,prelock_status='',
             prelock_starter='',prelock_role='Projected bench',confidence='medium',
             adjusted_minutes=20,adjusted_fd_points=22.0,projection_scored_at_utc='old')])
    updated = pool.assign(projection_scored_at_utc='new')
    assert compare_checkpoints(pool,updated).empty
    updated.loc[0,'prelock_status'] = 'out'
    updated.loc[0,'eligible'] = False
    updated.loc[1,'adjusted_minutes'] = 24
    updated.loc[1,'adjusted_fd_points'] = 25.5
    changes = compare_checkpoints(pool,updated).set_index('fanduel_id')
    assert len(changes) == 2
    assert 'eligible' in changes.loc['100-1','changes']
    assert 'prelock_status' in changes.loc['100-1','changes']
    assert changes.loc['100-2','minutes_delta'] == 4
    assert changes.loc['100-2','fd_delta'] == 3.5
    assert pool.loc[0,'eligible']
    assert compare_checkpoints(pool,pool.iloc[::-1]).empty
    assert 'coverage' in compare_checkpoints(pool,pool.assign(ceiling_fd_points=40)).iloc[0].changes
    with pytest.raises(ValueError,match='pools differ'):
        compare_checkpoints(pool,pool.iloc[:1])
    with pytest.raises(ValueError,match='identity'):
        compare_checkpoints(pool,pool.assign(salary=9999))
    with pytest.raises(ValueError,match='Unique'):
        compare_checkpoints(pool,pd.concat([pool,pool]))
