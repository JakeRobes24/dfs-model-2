import pytest
from forecast_revision_audit import revision_review


def test_revision_accuracy_and_rank_differ():
    rows=[dict(id='a', pos='WR', baseline=2, revised=7, actual=8),
          dict(id='b', pos='WR', baseline=1, revised=8, actual=5),
          dict(id='c', pos='WR', baseline=1, revised=1, actual=None)]
    result=revision_review(rows,group_field='pos')
    assert result['excluded']==1
    assert result['cohorts']['all']['baseline_mae']==5
    assert result['cohorts']['all']['revised_mae']==2
    assert result['rank_pairs']==1
    assert result['pair_weighted']=={'baseline':1,'revised':0}
    assert result['cohorts']['all']['improved']==2
    with pytest.raises(ValueError):
        revision_review(rows+rows[:1],group_field='pos')


def test_nba_fixed_rate_and_ties():
    rows=[dict(id='a', game='g', baseline=20, revised=24, actual=26,
               baseline_minutes=20, revised_minutes=24, actual_minutes=26),
          dict(id='b', game='g', baseline=20, revised=20, actual=18,
               baseline_minutes=20, revised_minutes=20, actual_minutes=18)]
    result=revision_review(rows,group_field='game',nba=True)
    assert result['components']['baseline_rate']==0
    assert result['components']['revised_rate']==0
    assert result['components']['minutes_only']==2
    assert result['components']['rate_only']==4
    assert result['equal_group']['baseline']==.5
    assert result['equal_group']['revised']==1
    assert result['cohorts']['all']['changed']==1
