import json
from pathlib import Path
import pytest
from nfl_opportunity_diagnostics import decompose_opportunity,audit_offensive_components
from nfl_daily_audit import audit_nfl_daily
from test_nfl_daily_audit import export,OFF
from test_nfl_contest_import import sample

def test_archived_backfield_error_decomposition():
    archive=json.loads((Path(__file__).parent/'docs/validation/nov25-backfield-exploratory.json').read_text())
    ids=[p['player_id'] for p in archive['pair']]
    actual=dict(zip(ids,archive['results']['actual_carries']))
    baseline=dict(zip(ids,[p['carries'] for p in archive['pair']]))
    shadow=dict(zip(ids,archive['results']['blended_carries']))
    for values in (baseline,shadow):
        r=decompose_opportunity(values,actual)
        assert sum(x['allocation_effect'] for x in r['rows'])==pytest.approx(0)
        assert sum(x['volume_effect'] for x in r['rows'])==pytest.approx(r['volume_error'])
        for x in r['rows']:
            assert x['volume_effect']+x['allocation_effect']==pytest.approx(x['error'])
    row=decompose_opportunity(baseline,actual)['rows'][0]
    assert row['volume_effect']==pytest.approx(9.61621338912134)
    assert row['allocation_effect']==pytest.approx(12.95378661087866)

@pytest.mark.parametrize('forecast,actual',[
    ({'a':1},{'b':1}),({'a':0},{'a':1}),({'a':1},{'a':0}),
    ({'a':-1},{'a':1}),({'a':float('nan')},{'a':1}),({'a':True},{'a':1})])
def test_invalid_opportunity_inputs(forecast,actual):
    with pytest.raises(ValueError):decompose_opportunity(forecast,actual)

def test_component_subtotal_and_missing_team_budget():
    a=audit_nfl_daily(sample(),export(OFF),contest_id='136799')
    r=audit_offensive_components(a)
    p=r['rows'][0]
    assert p['component_fields_complete']
    assert p['component_subtotal']==pytest.approx(18)
    assert p['daily_fd']==20.8
    assert p['residual_flag']
    assert r['rows'][1]['component_subtotal'] is None
    assert not r['certified']
    assert any(b['missing_ids'] for b in r['team_budgets'])

def test_missing_components_not_zero():
    a=audit_nfl_daily(sample(),export(OFF.replace(',250,',',,')),contest_id='136799')
    r=audit_offensive_components(a)
    assert r['rows'][0]['component_subtotal'] is None
    assert not r['rows'][0]['component_fields_complete']

def test_duplicate_id_rejected():
    a=audit_nfl_daily(sample(),export(OFF),contest_id='136799')
    a['players'].append(a['players'][0])
    with pytest.raises(ValueError):audit_offensive_components(a)
