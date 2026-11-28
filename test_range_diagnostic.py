import pytest
from range_diagnostic import interval_metrics,order_metrics,replay

def test_width_coverage_tradeoff():
    rows=[dict(fd_p10=90,fd_p50=100,fd_p90=110,actual=115)]
    assert interval_metrics(rows,1)['interval_score']==70
    assert interval_metrics(rows,1.5)['interval_score']==30
    assert interval_metrics(rows,2)['interval_score']==40
    with pytest.raises(ValueError):interval_metrics(rows,.5)

def test_neutral_and_ties():
    r=dict(lineup_ahead_share=.7,alternative_ahead_share=.2,tie_share=.1,actual_gap=5,reviewed_gap=3)
    assert order_metrics([r],0)['brier']==.25
    assert order_metrics([r],1)['brier']==pytest.approx(.0625)
    assert order_metrics([dict(r,actual_gap=0)],1)['n']==0
    with pytest.raises(ValueError):order_metrics([dict(r,tie_share=.3)],1)

def slate(day,actual):
    return dict(date=day,metadata=dict(captured_at=day+'T12:00:00+00:00',first_tip=day+'T23:00:00+00:00'),training=dict(training_latest='2026-10-01'),lineups=[dict(lineup='1',policy=p,fd_p10=90,fd_p50=100,fd_p90=110,actual=actual,reviewed=100) for p in ('point_residual','paired_minutes_rate')],pairs=[])

def test_training_only_and_common_support():
    a,b=slate('2026-11-22',115),slate('2026-11-24',100)
    r=replay([a,b]); assert r[1]['policies']['point_residual']['selected_width']==1.5
    b['lineups'][0]['actual']=200;b['lineups'][1]['actual']=200
    assert replay([a,b])[1]['policies']['point_residual']['selected_width']==1.5
    b['lineups'][1]['actual']=0
    with pytest.raises(ValueError):replay([a,b])
