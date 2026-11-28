import pytest
from portfolio_exposure_audit import audit_exposure


def fixture():
    return [dict(candidate_id=k,player_ids=p,projected_fd=v)
            for k,p,v in [('a',['x','y'],100),('b',['x','z'],99),
                          ('c',['y','z'],98),('d',['x','w'],97)]]


def test_opportunity_cost_and_overlap():
    r=audit_exposure(fixture(),['a','b'],entries=2,roster_size=2)
    assert r['feasible_portfolios']==6
    assert r['reference']['all_entry_core']==1
    assert r['reference']['average_pair_overlap']==1
    assert r['core_frontier'][0]['candidates']==('c','d')
    assert r['core_frontier'][0]['loss_vs_reference']==4
    assert r['player_challenges']['x']['alternative']['candidates']==('a','c')
    assert r['player_challenges']['x']['alternative']['loss_vs_reference']==1


def test_existing_requirement_and_no_feasible_challenge():
    r=audit_exposure(fixture(),['a','b'],entries=2,roster_size=2,required_exposure={'x':2})
    assert r['feasible_portfolios']==3
    assert r['player_challenges']['x']['alternative'] is None
    assert r['core_frontier'][0] is None
    with pytest.raises(ValueError):
        audit_exposure(fixture(),['a','c'],entries=2,roster_size=2,required_exposure={'x':2})


def test_fail_closed_for_duplicate_sets_and_large_search():
    data=fixture()
    with pytest.raises(ValueError):
        audit_exposure(data+[dict(data[0],candidate_id='e')],['a','b'],entries=2,roster_size=2)
    with pytest.raises(ValueError):
        audit_exposure(data,['a','b'],entries=2,roster_size=2,max_combinations=5)
