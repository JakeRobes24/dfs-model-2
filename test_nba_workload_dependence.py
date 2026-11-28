import pytest
from nba_workload_dependence import compare_workload_dependence,_score


def test_zero_relationship_preserves_distribution_and_centers():
    a=dict(id='1',team='BOS',minutes=30,center=35,actual=40)
    b=dict(id='2',team='BOS',minutes=20,center=20,actual=15)
    sd={0:5.,1:8.}
    baseline=_score([a,b],sd,{},'independent')
    assert _score([a,b],sd,{},'workload')==baseline
    positive=_score([a,b],sd,{('same',(0,1)):.3},'workload')
    assert positive['width']>baseline['width']
    assert positive['coverage']==baseline['coverage']


def test_reject_duplicate_and_invalid_game_and_insufficient_training():
    row=dict(date='2026-11-20',id='1',team='BOS',game='BOS@NYK',minutes=30,center=30,actual=31)
    assert compare_workload_dependence([row])==[]
    for rows in ([row,row],[dict(row,game='BOS@BOS')],[dict(row,actual=None)]):
        with pytest.raises(ValueError):
            compare_workload_dependence(rows)
