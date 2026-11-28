import pandas as pd
import pytest
from temporal_component_transfer import paired_archive, transfer_grid


def packet():
    return pd.DataFrame([
        dict(day=day, id=pid, policy=policy, actual=actual, value=value)
        for day,pid,actual,base,alt in [('2026-10-01','a',10,8,10),('2026-10-02','b',20,18,20)]
        for policy,value in [('base',base),('alt',alt)]])


def test_strict_common_archive():
    raw = packet()
    paired = paired_archive(raw,['day','id'],['base','alt'],actual='actual',forecast='value')
    assert paired.actual.tolist() == [10,20]
    assert paired.base.tolist() == [8,18]
    with pytest.raises(ValueError, match='Duplicate'):
        paired_archive(pd.concat([raw,raw.iloc[:1]]),['day','id'],['base','alt'],actual='actual',forecast='value')
    with pytest.raises(ValueError, match='Unequal'):
        paired_archive(raw.iloc[:-1],['day','id'],['base','alt'],actual='actual',forecast='value')
    raw.loc[1,'actual'] = 11
    with pytest.raises(ValueError, match='Mismatched'):
        paired_archive(raw,['day','id'],['base','alt'],actual='actual',forecast='value')


def test_weight_fixed_before_test_and_ties_prefer_baseline():
    train = pd.DataFrame(dict(day=['2026-10-01','2026-10-02'],base=[8,8],alt=[10,10],actual=[10,10]))
    test = pd.DataFrame(dict(day=['2026-10-03'],base=[8],alt=[10],actual=[8]))
    kwargs = dict(period='day',chronology='day',minimum_rows=2,minimum_periods=2)
    result = transfer_grid(train,test,'base','alt',**kwargs)
    assert result['weight'] == 1
    assert result['selected']['mae'] == 2
    assert transfer_grid(train.assign(alt=8),test,'base','alt',**kwargs)['weight'] == 0
    assert transfer_grid(train,test.assign(actual=100),'base','alt',**kwargs)['weight'] == 1
    assert transfer_grid(train.iloc[:1],test,'base','alt',**kwargs) is None
    with pytest.raises(ValueError,match='Training must end'):
        transfer_grid(train,test.assign(day='2026-10-02'),'base','alt',**kwargs)


def test_equal_period_weight_not_row_weight():
    train = pd.DataFrame(dict(day=['2026-10-01']*9+['2026-10-02'],base=[0]*10,alt=[10]*10,actual=[10]*9+[0]))
    test = pd.DataFrame(dict(day=['2026-10-03'],base=[0],alt=[10],actual=[5]))
    result = transfer_grid(train,test,'base','alt',period='day',chronology='day',minimum_rows=2,minimum_periods=2)
    assert result['weight'] == 0  # all weights tie with equal-period absolute loss
    assert result['training'][0]['mae'] == 5
