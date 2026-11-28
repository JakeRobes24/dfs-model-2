import pytest
from nba_player_choice_audit import player_choice_audit


def fixture():
    return [dict(date='2026-11-28',id=str(i),base=base,challenger=alt,actual=actual,salary=salary)
            for i,(base,alt,actual,salary) in enumerate([(30,32,40,6000),(31,29,20,6100),(50,50,50,9000)])]


def test_fixed_pair_membership_top_order_and_salary():
    base,alt=player_choice_audit(fixture(),forecasts=('base','challenger'),top_k=2)
    assert base['all_pairs']==alt['all_pairs']==3
    assert base['anchor_gap_le2_pairs']==alt['anchor_gap_le2_pairs']==1
    assert base['anchor_gap_le2_accuracy']==0
    assert alt['anchor_gap_le2_accuracy']==1
    assert base['salary_gap_le500_pairs']==alt['salary_gap_le500_pairs']==1
    assert base['top_actual_mean']==35
    assert alt['top_actual_mean']==45
    assert alt['top_actual_hits']==2


def test_ties_and_missing_salary_are_explicit():
    rows=fixture()
    rows[0]['challenger']=rows[1]['challenger']
    rows[0]['salary']=None
    base,alt=player_choice_audit(rows,forecasts=('base','challenger'))
    assert alt['anchor_gap_le2_accuracy']==.5
    assert 'salary_gap_le500_pairs' not in alt
    rows[0]['actual']=rows[1]['actual']
    assert player_choice_audit(rows,forecasts=('base','challenger'))[0]['anchor_gap_le2_pairs']==0


def test_common_support_and_identity_guards():
    rows=fixture()
    with pytest.raises(ValueError,match='Unique player ID'):
        player_choice_audit(rows+[rows[0]],forecasts=('base','challenger'))
    rows[0]['challenger']=None
    with pytest.raises(ValueError,match='Common finite'):
        player_choice_audit(rows,forecasts=('base','challenger'))
