import pytest
from nba_forward_component_reference import compare_capture


def fixture():
    row=dict(player='Example Player',team='ORL',game='ORL@WSH',tip_utc='2026-11-28T22:00:00Z')
    f=dict(minutes=20,minutes_lower80=12,minutes_upper80=28,
           points=10,rebounds=4,assists=2,steals=1,turnovers=1,threes=1)
    capture=dict(schema=1,reviewed_at='2026-11-28T11:49:25Z',
                 sources={'house':{'published_at':None},'capper':{'published_at':'2026-11-28T07:31:00Z'}},
                 rows=[dict(row,house_minutes=15,capper=f)])
    actual=dict(row,official_player_id='1',identity_verified=True,source='official',
                final=True,observed_at='2026-11-29T01:00:00Z',participation='played',
                minutes=25,components={k:v for k,v in f.items() if not k.startswith('minutes')})
    return capture,actual


def test_minutes_and_partial_rate():
    c,a=fixture()
    report=compare_capture(c,[a])
    assert report['minutes']['all']['house']['mae']==10
    assert report['minutes']['all']['capper']['mae']==5
    assert report['capper_nominal80_minutes']['coverage']==1
    assert report['capper_nominal80_minutes']['interval_score']==16
    assert report['partial_fd_without_blocks']['capper']['mae']==0
    assert report['partial_fd_without_blocks']['house_minutes_capper_rate']['mae']==pytest.approx(4.95)
    assert report['certified'] is False


def test_missing_and_timing():
    c,a=fixture()
    assert compare_capture(c,[])['coverage']=={'unmatched':1}
    assert compare_capture(c,[dict(a,participation='unknown')])['minutes']=={}
    a['components'].pop('steals')
    assert compare_capture(c,[a])['partial_fd_without_blocks']['capper']['n']==0
    with pytest.raises(ValueError):
        compare_capture(c,[a,a])
    with pytest.raises(ValueError):
        compare_capture(dict(c,reviewed_at=a['tip_utc']),[a])


def test_partial_fd_attribution_uses_paired_minutes_and_rate():
    c,a=fixture()
    r=compare_capture(c,[a])['partial_fd_error_attribution']['all']
    assert r['n']==1
    assert r['total_bias']==0
    assert r['volume_bias']+r['rate_bias']==pytest.approx(0)
    assert r['volume_bias']<0<r['rate_bias']
