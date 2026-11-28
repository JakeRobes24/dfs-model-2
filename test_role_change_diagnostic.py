import pandas as pd
import pytest
from role_change_diagnostic import role_range_comparison


def test_frozen_earlier_radii_and_fallback():
    train=pd.DataFrame(dict(day=[1,1,2,2],trigger=[True,True,False,False],y=[0,2,0,4],p=[0,0,0,0]))
    test=pd.DataFrame(dict(day=[3,3],trigger=[True,False],y=[1,5],p=[0,0]))
    r=role_range_comparison(train,test,period='day',actual='y',forecast='p',min_group=2)
    assert r['pooled_radius']==4
    assert r['role_radii']=={True:2,False:4}
    assert r['scores']['role']['coverage']==.5
    changed=role_range_comparison(train,test.assign(y=100),period='day',actual='y',forecast='p',min_group=2)
    assert changed['role_radii']==r['role_radii']
    fallback=role_range_comparison(train,test,period='day',actual='y',forecast='p',min_group=3)
    assert fallback['role_radii']=={True:4,False:4}
    with pytest.raises(ValueError):
        role_range_comparison(train,test.assign(day=2),period='day',actual='y',forecast='p')
    with pytest.raises(ValueError):
        role_range_comparison(train,test.assign(trigger='unknown'),period='day',actual='y',forecast='p')
