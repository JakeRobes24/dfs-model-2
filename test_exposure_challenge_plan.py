import pytest
from exposure_challenge_plan import exposure_challenge_plan

def test_shared_core_plan_and_explicit_truncation():
    r=[['a','b','c'],['a','b','d'],['a','b','e'],['a','c','d']]
    x=exposure_challenge_plan(r)
    assert x['targets']==['a','b']
    assert x['scenarios']==[('a',),('b',)]
    y=exposure_challenge_plan(r,max_targets=1)
    assert y['unreviewed_targets']==['b']
    assert not y['complete_target_plan']

def test_all_entry_pair_and_validation():
    r=[['a','b','c'],['a','b','d'],['a','b','e']]
    assert exposure_challenge_plan(r)['scenarios']==[('a',),('b',),('a','b')]
    with pytest.raises(ValueError):exposure_challenge_plan([r[0],r[0]])
    with pytest.raises(ValueError):exposure_challenge_plan(r,minimum_count=1)
