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
