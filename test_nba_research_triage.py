import pandas as pd
from nba_research_triage import disagreement_queue


def test_disagreement_queue_distinguishes_consensus_conflict_and_missing():
    pool = pd.DataFrame({
        'fanduel_id': list('abcdef'), 'fanduel_name': list('ABCDEF'),
        'eligible': [True, True, True, True, False, True], 'salary': 5000,
        'projected_fd_points': 30, 'adjusted_fd_points': [30,30,30,0,30,30],
        'independent_fd_points': [42,42,38,None,50,31],
        'projection_source_count': [2,2,1,0,2,2],
        'projection_source_spread': [2,9,0,None,1,1],
        'projected_minutes': 25, 'independent_minutes': [32,25,25,None,25,25],
        'recent_mpg': [32,25,25,None,25,25], 'blend_status': 'unchanged',
    })
    original = pool.copy(deep=True)
    queue = disagreement_queue(pool)
    assert queue.fanduel_id.tolist() == ['d','a','b','c']
    reasons = queue.set_index('fanduel_id').review_reason
    assert 'Agreeing providers differ from DAILY' in reasons.a
    assert 'Independent minutes differ' in reasons.a
    assert 'Recent rotation differs' in reasons.a
    assert 'providers conflict' in reasons.b
    assert 'Agreeing providers' not in reasons.b
    assert 'Single-source' in reasons.c
    assert 'Missing usable' in reasons.d
    pd.testing.assert_frame_equal(pool, original)
    assert disagreement_queue(pool.iloc[0:0]).empty


def test_paired_gap_decomposition_never_borrows_other_provider_minutes():
    import json
    import pytest
    from nba_research_triage import paired_gap_breakdown

    def evaluate(*notes):
        return paired_gap_breakdown(30, 30, json.dumps(notes))

    minutes_only = dict(family='a', points=40, paired_minutes=40, weight=1)
    rate_only = dict(family='b', points=45, paired_minutes=30, weight=.5)
    unpaired = dict(family='c', points=90, weight=1)
    one = evaluate(minutes_only, unpaired)
    assert one['paired_source_count'] == 1
    assert one['time_effect'] == 10
    assert one['rate_effect'] == 0
    assert one['paired_gap_driver'] == 'Mainly projected minutes'
    two = evaluate(rate_only)
    assert two['time_effect'] == 0 and two['rate_effect'] == 15
    assert two['paired_gap_driver'] == 'Mainly projected production rate'
    both = evaluate(minutes_only, rate_only, unpaired)
    assert both['paired_source_count'] == 2
    assert both['paired_point_gap'] == pytest.approx(17.5 / 1.5)
    assert both['time_effect'] + both['rate_effect'] == pytest.approx(both['paired_point_gap'])
    assert evaluate(unpaired)['paired_gap_driver'] == 'Paired evidence unavailable'
    assert evaluate(minutes_only, minutes_only)['paired_source_count'] == 0
    offset = evaluate(dict(family='a', points=30, paired_minutes=40, weight=1))
    assert offset['paired_gap_driver'] == 'Offsetting time and rate effects'
    assert offset['time_effect'] + offset['rate_effect'] == pytest.approx(0)


def test_historical_rate_context_preserves_missing_and_small_samples():
    import pytest
    from nba_research_triage import attach_rate_context
    queue = pd.DataFrame({'fanduel_id': ['a','b','c'], 'projected_fd_points': [30,30,30],
                          'projected_minutes': [30,30,0], 'paired_projected_fppm': [1.5,1.2,None]})
    history = pd.DataFrame({'fanduel_id': ['a','b'], 'FD points per minute': [1.1,.8],
                            'Games with complete FD stats': [3,1],
                            'Minutes with complete FD stats': [90,15],
                            'Shot/FT/turnover opportunities per minute': [.7,.4],
                            'Box-score sources': ['official a','official b']})
    result = attach_rate_context(queue, history).set_index('fanduel_id')
    assert result.loc['a','paired_rate_vs_history'] == pytest.approx(.4)
    assert result.loc['a','daily_rate_vs_history'] == pytest.approx(-.1)
    assert result.loc['a','historical_rate_context'].startswith('Recent observed')
    assert result.loc['b','historical_rate_context'] == 'Small observed sample'
    assert pd.isna(result.loc['c','daily_fppm'])
    assert pd.isna(result.loc['c','observed_fppm'])
    assert result.loc['c','historical_rate_context'].startswith('No complete')
    assert attach_rate_context(queue, pd.DataFrame()).observed_fppm.isna().all()
    with pytest.raises(ValueError):
        attach_rate_context(queue, pd.concat([history, history]))


def test_team_news_review_is_contest_scoped_and_nonmutating():
    import json
    from nba_research_triage import team_opportunity_review
    base = dict(team='DET',game='DET@ORL',eligible=True,prelock_status='',
                prelock_starter='',prelock_role='',adjusted_minutes=24.,
                adjusted_fd_points=20.,projection_sources_json='[]')
    pool = pd.DataFrame([dict(base,fanduel_id='1-a',fanduel_name='Absent',eligible=False,prelock_status='out'),
        dict(base,fanduel_id='1-b',fanduel_name='Replacement',prelock_starter='starter',prelock_role='Projected bench'),
        dict(base,fanduel_id='1-c',fanduel_name='Teammate',projection_sources_json=json.dumps([
            dict(family='a',points=22,observed_at='2026-11-24T23:02:00Z'),
            dict(family='b',points=23,observed_at='2026-11-24T23:03:00Z'),
            dict(family='c',points=25,observed_at='2026-11-24T23:30:00Z')])),
        dict(base,fanduel_id='1-d',fanduel_name='Opponent',team='ORL'),
        dict(base,fanduel_id='1-e',fanduel_name='Other game',game='DET@BOS')])
    def note(pid,stamp,**kw):
        return dict(dict(fanduel_id=pid,official=False,review='Reviewed',observed_at=stamp,
                         status='',starter='',minutes=None,independent_group=''),**kw)
    notes = pd.DataFrame([
        note('1-a','2026-11-24T22:50:00Z',official=True,status='out'),
        note('1-b','2026-11-24T23:00:00Z',official=True,starter='starter'),
        note('1-b','2026-11-24T22:55:00Z',minutes=20,independent_group='a'),
        note('1-b','2026-11-24T23:01:00Z',minutes=28,independent_group='a'),
        note('1-c','2026-11-24T23:01:00Z',minutes=25,independent_group='a'),
        note('1-c','2026-11-24T23:02:00Z',minutes=26,independent_group='b'),
        note('1-c','2026-11-24T23:30:00Z',minutes=28,independent_group='c'),
        note('1-c','2026-11-24T23:04:00Z',minutes=24,independent_group='d',review='Stale')])
    original=pool.copy(deep=True)
    result=team_opportunity_review(pool,notes,'2026-11-24T23:10:00Z').set_index('fanduel_id')
    assert set(result.index)=={'1-b','1-c'}
    assert result.loc['1-b','Minutes families since confirmation']==1
    assert result.loc['1-b','Points families since confirmation']==0
    assert result.loc['1-c','Minutes families since confirmation']==2
    assert result.loc['1-c','Points families since confirmation']==2
    assert 'Recheck production' in result.loc['1-b','Opportunity review']
    assert 'incorporated news' in result.loc['1-c','Opportunity review']
    pd.testing.assert_frame_equal(pool,original)
    conflict=note('1-a','2026-11-24T22:50:00Z',official=True,status='available')
    out=team_opportunity_review(pool,pd.concat([notes,pd.DataFrame([conflict])]),'2026-11-24T23:10:00Z')
    assert not out['Confirmed events'].str.contains('Absent').any()
    assert team_opportunity_review(pool,notes.iloc[0:0],'2026-11-24T23:10:00Z').empty


def test_paired_source_coverage_keeps_points_only_and_stale_evidence_separate():
    import json
    import pytest
    from nba_research_triage import paired_source_coverage
    from slate_research import PROPSIMS, ROTOGRINDERS, DFF
    now='2026-11-25T23:00:00Z'
    def note(family,minutes,stamp='2026-11-25T22:00:00Z',points=30):
        source, name = {'a':(PROPSIMS,'propsims'),'b':(ROTOGRINDERS,'rotogrinders'),'c':(DFF,'daily-fantasy-fuel')}[family]
        return dict(source=source,family=name,points=points,paired_minutes=minutes,observed_at=stamp)
    pool=pd.DataFrame([
        dict(fanduel_id='1-1',eligible=True,projection_sources_json=json.dumps([
            note('a',30),note('b',None),note('c',25,'2026-11-25T15:00:00Z')])),
        dict(fanduel_id='1-2',eligible=True,projection_sources_json=json.dumps([
            note('a',30),note('b',25),note('c',20,'2026-11-25T23:01:00Z')])),
        dict(fanduel_id='1-3',eligible=True,projection_sources_json=json.dumps([
            note('a',30),note('a',35),note('b',0)])),
        dict(fanduel_id='1-4',eligible=False,projection_sources_json=json.dumps([note('c',30)]))])
    original=pool.copy(deep=True)
    players,providers=paired_source_coverage(pool,now)
    assert players['Paired providers'].tolist()==[1,2,0]
    summary=providers.set_index('Provider')
    assert summary['Fresh point players'].to_dict()=={'propsims':2,'rotogrinders':3}
    assert summary['Fresh paired players'].to_dict()=={'propsims':2,'rotogrinders':1}
    pd.testing.assert_frame_equal(pool,original)
    with pytest.raises(ValueError):
        paired_source_coverage(pool,'2026-11-25 23:00')


def test_paired_coverage_rejects_unregistered_or_spoofed_families():
    import json
    from nba_research_triage import paired_source_coverage
    from slate_research import PROPSIMS, ROTOGRINDERS
    base = dict(source=PROPSIMS,family='propsims',points=30,paired_minutes=30,
                observed_at='2026-11-25T22:00:00Z')
    notes = [base, dict(base, family='rotogrinders'),
             dict(base, source='https://unknown.example/',family='unknown'),
             dict(base, source=ROTOGRINDERS,family='invented')]
    pool = pd.DataFrame([dict(fanduel_id='1-1', eligible=True,
                              projection_sources_json=json.dumps(notes))])
    players, providers = paired_source_coverage(pool,'2026-11-25T23:00:00Z')
    assert players['Paired providers'].tolist() == [1]
    assert providers['Provider'].tolist() == ['propsims']
