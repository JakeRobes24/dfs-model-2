from copy import deepcopy
import pytest
from test_nfl_expected_opportunity_shadow import fixture,NOW
from nfl_expected_opportunity_shadow import freeze_expected_opportunity
from nfl_expected_opportunity_outcomes import compare_frozen_opportunity


def inputs():
    audit,packet=fixture()
    receipt=freeze_expected_opportunity(audit,packet,frozen_at=NOW)
    actual=dict(player_id='100-1',gsis_id='00-1',team='CIN',game='NO@CIN',position='WR',
                season=2026,game_date='2026-11-29',kickoff_utc='2026-11-29T18:00:00Z',
                official_game_id='official-game',identity_verified=True,source='official gamebook',
                source_record_id='official-row',final=True,final_at='2026-11-29T21:00:00Z',
                observed_at='2026-11-29T22:00:00Z',participation='played',
                components=dict(receptions=6,rec_yards_gained=80,rec_touchdown=0,rec_two_point_conv=0))
    return audit,packet,receipt,actual


def test_same_support_actual_and_expected_forecasts():
    a,p,r,x=inputs()
    result=compare_frozen_opportunity(a,p,r,[x])
    row=next(y for y in result['summary'] if y['position']=='all')
    assert row['n']==1
    assert row['errors']['actual_average']['mae']==3
    assert row['errors']['challenger']['mae']==pytest.approx(.375)
    assert row['improved']==1
    assert result['coverage']=={'matched_played':1,'unsupported_forecast':1}
    assert not result['certified']


def test_receipt_tampering_rejected():
    a,p,r,x=inputs()
    r['rows'][0]['channels']['receiving']['challenger']=99
    with pytest.raises(ValueError):
        compare_frozen_opportunity(a,p,r,[x])


def test_missing_fields_and_nonparticipation_not_imputed():
    a,p,r,x=inputs()
    assert compare_frozen_opportunity(a,p,r,[])['coverage']['missing_outcome']==1
    assert compare_frozen_opportunity(a,p,r,[dict(x,participation='inactive')])['summary']==[]
    x['components'].pop('rec_two_point_conv')
    result=compare_frozen_opportunity(a,p,r,[x])
    assert result['coverage']['missing_or_invalid_channel']==1
    assert result['summary']==[]


def test_wrong_identity_and_chronology_rejected():
    a,p,r,x=inputs()
    for actual in (dict(x,gsis_id='00-2'),dict(x,game='CIN@NO'),
                   dict(x,final_at=x['kickoff_utc']),dict(x,source_record_id='')):
        with pytest.raises(ValueError):
            compare_frozen_opportunity(a,p,r,[actual])
    with pytest.raises(ValueError):
        compare_frozen_opportunity(a,p,r,[x,x])
