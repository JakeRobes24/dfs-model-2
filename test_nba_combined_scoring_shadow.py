import json
import pandas as pd
import pytest
from nba_combined_scoring_shadow import reviewed_minutes_shadow


def test_combined_points_are_not_scaled_twice_and_unsupported_stays_missing():
    sources=[dict(family='a',points=36.,weight=1.,paired_minutes=30.),
             dict(family='b',points=40.,weight=1.,paired_minutes=None)]
    row=dict(fanduel_id='1',eligible=True,injury_flag='',prelock_status='',
             minutes_method='prelock_independent_consensus',
             blend_status='Minutes/status adjustment takes priority',
             adjusted_minutes=31.,adjusted_fd_points=42.,
             independent_fd_points=38.,projection_source_count=2,projection_source_spread=4.,
             projection_sources_json=json.dumps(sources))
    result=reviewed_minutes_shadow(pd.DataFrame([row]))
    assert result.shadow_combined_fd.iloc[0]==pytest.approx(40.4)
    for changes in (dict(eligible=False),dict(prelock_status='questionable'),
                    dict(blend_status='Independent sources disagree'),
                    dict(adjusted_minutes=35),dict(independent_fd_points=39),
                    dict(projection_source_count=1),dict(projection_sources_json='[]')):
        assert pd.isna(reviewed_minutes_shadow(pd.DataFrame([dict(row,**changes)])).shadow_combined_fd.iloc[0])
    assert row['adjusted_fd_points']==42.


def test_combined_evaluation_scores_identical_verified_played_rows():
    from nba_combined_scoring_shadow import compare_combined_shadow
    row=dict(fanduel_id='1',eligible=True,injury_flag='',prelock_status='',
             minutes_method='prelock_independent_consensus',blend_status='Minutes/status adjustment takes priority',
             adjusted_minutes=31.,adjusted_fd_points=42.,independent_fd_points=38.,
             projection_source_count=2,projection_source_spread=4.,
             projection_sources_json=json.dumps([dict(family='a',points=36.,weight=1.,paired_minutes=30.),
                                                 dict(family='b',points=40.,weight=1.,paired_minutes=None)]))
    pool=pd.DataFrame([row,dict(row,fanduel_id='2')])
    replay=pd.DataFrame(dict(fanduel_id=['1','2'],verified_outcome=['played','needs_review'],
                             nba_source=['NBA official box',''],actual_points=[39.,0.],
                             daily_points=[32.,32.],adjusted_fd_points=[42.,42.]))
    report=compare_combined_shadow(pool,replay).iloc[0]
    assert report['Paired players']==1
    assert report['Reviewed MAE']==pytest.approx(3)
    assert report['Experimental MAE']==pytest.approx(1.4)


def test_paired_rate_normalizes_minutes_once_and_rejects_old_team_evidence():
    import json
    from nba_combined_scoring_shadow import paired_rate_shadow, compare_frozen_paired_rate
    from slate_research import PROPSIMS, ROTOGRINDERS
    capture = '2026-11-25T23:00:00Z'
    estimates = [
        dict(source=PROPSIMS,family='propsims',points=36.,paired_minutes=30.,weight=1.,observed_at='2026-11-25T22:30:00Z'),
        dict(source=ROTOGRINDERS,family='rotogrinders',points=42.,paired_minutes=35.,weight=1.,observed_at='2026-11-25T22:40:00Z')]
    base = dict(fanduel_id='1-1',team='DET',game='DET@ORL',eligible=True,injury_flag='',
                prelock_status='',prelock_starter='starter',minutes_method='prelock_independent_consensus',
                blend_status='Minutes/status adjustment takes priority',adjusted_minutes=32.,
                adjusted_fd_points=32.,independent_fd_points=39.,projection_source_count=2,
                projection_source_spread=6.,projection_sources_json=json.dumps(estimates),
                replay_evidence_json='[]',replay_captured_at_utc=capture,verified_outcome='played',
                nba_source='NBA box',actual_points=35.,daily_points=30.)
    scratch = dict(base,fanduel_id='1-2',eligible=False,prelock_status='out',
                   replay_evidence_json=json.dumps([dict(official=True,status='out',starter='',
                                                         observed_at='2026-11-25T22:20:00Z')]))
    data = pd.DataFrame([base,scratch])
    original = data.copy(deep=True)
    result = paired_rate_shadow(data).set_index('fanduel_id')
    assert result.loc['1-1','shadow_rate_fd'] == pytest.approx(34.56)
    assert result.loc['1-1','rate_source_count'] == 2
    assert pd.isna(result.loc['1-2','shadow_rate_fd'])
    review = compare_frozen_paired_rate(data).iloc[0]
    assert review['Paired players'] == 1
    assert review['Eligible players reviewed for rate blend'] == 1
    assert review['Eligible with two fresh paired sources'] == 1
    assert review['Eligible supported rate forecasts'] == 1
    pd.testing.assert_frame_equal(data,original)
    for notes in [
        [dict(estimates[0], observed_at='2026-11-25T22:00:00Z'),estimates[1]],
        [dict(estimates[0], paired_minutes=None),estimates[1]],
        [estimates[0],dict(estimates[1],family='propsims')],
        [estimates[0],dict(estimates[1],source=PROPSIMS)],
        [estimates[0],dict(estimates[1],source='https://unknown.example/')],
        [estimates[0],dict(estimates[1],points=60.)],
        [estimates[0],dict(estimates[1],observed_at='2026-11-25T23:01:00Z')],
    ]:
        bad = data.copy()
        bad.loc[0,'projection_sources_json'] = json.dumps(notes)
        assert pd.isna(paired_rate_shadow(bad).iloc[0].shadow_rate_fd)
    unrelated = data.copy()
    unrelated.loc[1,'game'] = 'DET@BOS'
    unrelated.loc[0,'projection_sources_json'] = json.dumps([
        dict(estimates[0],observed_at='2026-11-25T22:00:00Z'),estimates[1]])
    assert paired_rate_shadow(unrelated).iloc[0].shadow_rate_fd == pytest.approx(34.56)
    assert paired_rate_shadow(data.drop(columns='replay_evidence_json')).empty
