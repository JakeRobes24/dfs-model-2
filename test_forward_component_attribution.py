import pytest
from forward_component_attribution import attribute, summarize_attribution

def test_exact_symmetric_decomposition():
    a=attribute(20,10,40,30)
    assert a=={'volume':25,'rate':-15,'total':10}
    assert a['volume']+a['rate']==a['total']
    report=summarize_attribution([a,attribute(10,20,30,40)])
    assert report['volume_mae']==25 and report['rate_mae']==15
    assert report['total_mae']==10 and report['total_bias']==0
    assert attribute(0,10,0,30) is None
    assert attribute(10,10,float('nan'),30) is None
    assert summarize_attribution([])['total_mae'] is None
