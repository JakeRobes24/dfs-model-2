import pandas as pd
import pytest
from provider_common_support import common_provider_comparison


def fixture():
    return pd.DataFrame([
        dict(date='2026-11-24',contest_id='1',player_id='1-1',metric='FD',timing_scope='timed',y=10,a=12,b=9),
        dict(date='2026-11-24',contest_id='1',player_id='1-2',metric='FD',timing_scope='timed',y=30,a=30,b=None),
        dict(date='2026-11-25',contest_id='2',player_id='2-1',metric='FD',timing_scope='recovered',y=20,a=25,b=23),
    ])


def test_common_support_and_timing():
    x=common_provider_comparison(fixture(),forecasts=['a','b'],actual='y')
    t=x[x.timing_scope.eq('timed')].set_index('forecast')
    assert t.common_players.tolist()==[1,1]
    assert t.available_forecasts.tolist()==[2,1]
    assert t.mae.tolist()==[2,1]
    assert t.bias.tolist()==[2,-1]
    assert set(x.timing_scope)=={'timed','recovered'}


def test_reject_duplicate_capture_and_mixed_contests():
    f=fixture()
    for bad in [pd.concat([f,f.iloc[:1]]),
                f.assign(contest_id=['1','3','2']),
                f.assign(timing_scope=['timed','recovered','recovered'])]:
        with pytest.raises(ValueError):
            common_provider_comparison(bad,forecasts=['a','b'],actual='y')
