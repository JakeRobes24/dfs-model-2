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


def test_fingerprint_tracks_exact_solver_and_review_inputs():
    from nba_checkpoint_changes import CANDIDATE_FIELDS, candidate_fingerprint
    row = {field: '' for field in CANDIDATE_FIELDS}
    row.update(fanduel_id='1-1', salary=4000, eligible=True, adjusted_minutes=24.0,
               adjusted_fd_points=30.0, confidence='medium', team='BOS', game='BOS@NYK',
               roster_eligibility='PG', fanduel_name='Alpha')
    pool = pd.DataFrame([row, dict(row, fanduel_id='1-2', fanduel_name='Beta')])
    scope = ('123','2026-11-25','contest-hash','daily-hash')
    def key(frame, scopes=scope, overlap=7, exclude=False, objective='adjusted_fd_points'):
        return candidate_fingerprint(frame,scopes,overlap,exclude,objective)
    baseline = key(pool)
    assert key(pool.assign(projection_scored_at_utc='new')) == baseline
    assert key(pool.iloc[::-1]) == baseline
    for column,value in [('adjusted_fd_points',30.00001),('adjusted_minutes',24.00001),
                         ('eligible',False),('prelock_status','out'),('prelock_starter','starter'),
                         ('confidence','low'),('salary',4100),('roster_eligibility','SG'),
                         ('team','NYK'),('research_attention','Review status'),
                         ('minutes_method','new method')]:
        revised = pool.copy()
        revised.loc[0,column] = value
        assert key(revised) != baseline, column
    assert key(pool,overlap=6) != baseline
    assert key(pool,exclude=True) != baseline
    assert key(pool,scopes=(*scope[:-1],'new-daily')) != baseline
    assert key(pool.assign(ceiling_fd_points=40)) != baseline
    assert key(pool.assign(gpp_objective=35,ceiling_fd_points=40),objective='gpp_objective') != baseline


def test_reuse_requires_complete_proven_optimal_portfolio_and_rival():
    from nba_checkpoint_changes import can_reuse_candidates
    lineups = pd.DataFrame([dict(lineup=i,fanduel_id=str(j),solver_optimal=True,team_rules_verified=True)
                            for i in range(1,5) for j in range(9)])
    alternative = lineups.iloc[:9].copy()
    comparison = pd.DataFrame({'Lineup':[1,2,3,4],'Alternative proven optimal':[True]*4})
    assert can_reuse_candidates((lineups,comparison,alternative))
    assert not can_reuse_candidates((lineups.iloc[:-1],comparison,alternative))
    assert not can_reuse_candidates((lineups,comparison.iloc[:-1],alternative))
    assert not can_reuse_candidates((lineups,comparison,alternative.assign(solver_optimal=False)))
    assert not can_reuse_candidates((lineups.assign(team_rules_verified=False),comparison,alternative))
    assert not can_reuse_candidates((lineups,comparison,pd.DataFrame()))


def test_portfolio_exposure_distinguishes_own_projection_and_other_combinations():
    from nba_checkpoint_changes import compare_portfolio_exposure
    base=dict(team='BOS',game='BOS@NYK',salary=5000,roster_eligibility='PG',
              eligible=True,prelock_status='',prelock_starter='',prelock_role='',
              confidence='medium',adjusted_minutes=30.,adjusted_fd_points=30.)
    pool=pd.DataFrame([dict(base,fanduel_id=f'1-{i}',fanduel_name=f'Player {i}') for i in range(11)])
    old=pd.DataFrame([dict(lineup=j,fanduel_id=f'1-{i}') for j in range(1,5) for i in range(9)])
    new=old.copy()
    new.loc[new.fanduel_id.eq('1-0'),'fanduel_id']='1-9'
    new.loc[new.fanduel_id.eq('1-1'),'fanduel_id']='1-10'
    current=pool.copy()
    current.loc[current.fanduel_id.eq('1-0'),'adjusted_fd_points']=25
    result=compare_portfolio_exposure(pool,current,old,new).set_index('fanduel_id')
    assert result.loc['1-0','observed_evidence']=='Own projection fell'
    assert result.loc['1-1','observed_evidence'].startswith('Own projection unchanged')
    assert result.loc['1-0','exposure_delta']==-4
    assert result.loc['1-9','exposure_delta']==4
    assert result.exposure_delta.sum()==0
    assert compare_portfolio_exposure(pool,pool,old,old.iloc[::-1]).empty
    with pytest.raises(ValueError):
        compare_portfolio_exposure(pool,current,old,new.iloc[:-1])
