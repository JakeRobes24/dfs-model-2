import copy
import pytest
from nfl_forward_component_reference import compare_capture


def fixture():
    row=dict(player='Example Player',team='CIN',game='NO@CIN',position='WR',
             kickoff_utc='2026-11-29T18:00:00Z')
    capture=dict(schema=1,reviewed_at='2026-11-28T11:44:26Z',
                 sources={'Volt Fantasy':{'published_at':None},
                          'Malter Analytics':{'published_at':'2026-11-28T11:17:00Z'}},
                 rows=[dict(row,forecasts={'Volt Fantasy':{'targets':8,'receptions':5,'receiving_yards':70},
                                           'Malter Analytics':{'receptions':6,'receiving_yards':75}})])
    actual=dict(row,official_player_id='official-1',identity_verified=True,
                source='official final record',final=True,observed_at='2026-11-29T22:00:00Z',
                participation='played',components={'targets':9,'receptions':4})
    return capture,actual


def test_same_component_support_and_unknown_publication():
    capture,actual=fixture()
    report=compare_capture(capture,[actual])
    assert report['coverage']=={'matched_played':1}
    assert len(report['comparison'])==1
    assert report['comparison'][0]['metric']=='receptions'
    assert report['comparison'][0]['errors']['Volt Fantasy']['mae']==1
    assert report['comparison'][0]['errors']['Malter Analytics']['mae']==2
    assert report['publication_unknown']==['Volt Fantasy']
    assert report['certified'] is False


def test_unknown_outcomes_and_time_leakage():
    capture,actual=fixture()
    assert compare_capture(capture,[])['coverage']=={'unmatched_outcome':1}
    assert compare_capture(capture,[dict(actual,participation='unknown')])['comparison']==[]
    assert compare_capture(capture,[dict(actual,final=False)])['comparison']==[]
    with pytest.raises(ValueError):
        compare_capture(capture,[dict(actual,identity_verified=False)])
    with pytest.raises(ValueError):
        compare_capture(capture,[actual,actual])
    with pytest.raises(ValueError):
        compare_capture(dict(capture,reviewed_at=actual['kickoff_utc']),[actual])
    bad=copy.deepcopy(capture)
    bad['sources']['Malter Analytics']['published_at']='2026-11-29T01:00:00Z'
    with pytest.raises(ValueError):
        compare_capture(bad,[actual])
