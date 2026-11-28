from copy import deepcopy
import pytest
from nfl_expected_opportunity_shadow import freeze_expected_opportunity

NOW='2026-11-28T12:00:00Z'
def fixture():
    audit=dict(contest_id='100',contest_sha256='a'*64,daily_sha256='b'*64,
               players=[dict(player_id='100-1',player='Example Player',team='CIN',game='NO@CIN',
                             positions=['WR'],status='unknown',projection_fd=15),
                        dict(player_id='100-2',player='Missing Player',team='NO',game='NO@CIN',
                             positions=['RB'],status='unknown',projection_fd=None)])
    history=[]
    for i,day in enumerate(['2026-11-01','2026-11-08','2026-11-15','2026-11-22'],8):
        actual=dict(receptions=4,rec_yards_gained=60,rec_touchdown=0,rec_two_point_conv=0,rec_attempt=8)
        expected=dict(receptions=5,rec_yards_gained=70,rec_touchdown=.5,rec_two_point_conv=0)
        history.append(dict(team_game_number=i,game_date=day,game_id='game'+str(i),gsis_id='00-1',
                            team='CIN',position='WR',season=2026,season_type='regular',participation='played',
                            source_identity_verified=True,expected_provenance_verified=True,
                            workload_source='verified game stats',expected_source='expected component source',
                            expected_record_id='expected'+str(i),workload_record_id='workload'+str(i),
                            game_final_at=day+'T21:00:00Z',expected_published_at=day+'T22:00:00Z',
                            expected_observed_at=day+'T23:00:00Z',workload_observed_at=day+'T23:00:00Z',
                            actual_components=actual,expected_components=expected,workload=dict(targets=8,receiving_yards=60)))
    packet=dict(schema=1,season=2026,contest_id='100',contest_sha256='a'*64,daily_sha256='b'*64,
                slate_date='2026-11-29',cutoff_utc='2026-11-29T17:30:00Z',
                players=[dict(player_id='100-1',gsis_id='00-1',identity_verified=True,schedule_verified=True,
                              team='CIN',game='NO@CIN',position='WR',kickoff_utc='2026-11-29T18:00:00Z',
                              team_game_number=12,history=history)])
    return audit,packet


def test_fixed_prior_channel_and_missing_rows():
    a,p=fixture()
    old=deepcopy(a)
    report=freeze_expected_opportunity(a,p,frozen_at=NOW)
    r=report['rows'][0]['channels']['receiving']
    assert r['actual_average']==8
    assert r['expected_average']==12.5
    assert r['challenger']==pytest.approx(11.375)
    assert r['prior_opportunities']==32
    assert report['rows'][1]['support']=='no_history_packet'
    assert report['certified'] is False
    assert len(report['history_packet_sha256'])==64
    assert a==old


def test_future_or_missing_evidence_is_not_filled():
    a,p=fixture()
    p['players'][0]['history'][0]['expected_observed_at']='2026-11-29T12:00:00Z'
    assert freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['support']=='unverified_prior_provenance'
    a,p=fixture()
    p['players'][0]['history'].pop(1)
    assert freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['support']=='missing_consecutive_prior_games'
    a,p=fixture()
    p['players'][0]['history'][0]['workload']['targets']=7
    assert freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['channels']=={}
    a,p=fixture()
    p['players'][0]['history'][0]['expected_provenance_verified']=False
    assert freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['channels']=={}


def test_cutoff_hash_duplicate_and_status_gates():
    a,p=fixture()
    with pytest.raises(ValueError):
        freeze_expected_opportunity(a,p,frozen_at='2026-11-29T17:31:00Z')
    with pytest.raises(ValueError):
        freeze_expected_opportunity(a,dict(p,daily_sha256='c'*64),frozen_at=NOW)
    with pytest.raises(ValueError):
        freeze_expected_opportunity(a,dict(p,players=p['players']*2),frozen_at=NOW)
    a['players'][0]['status']='questionable'
    assert freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['support']=='uncertain_or_unavailable_contest_status'


def test_rushing_weight_and_season_gate():
    a,p=fixture()
    a['players'][0]['positions']=['RB']
    record=p['players'][0]
    record['position']='RB'
    for r in record['history']:
        r['position']='RB'
        r['actual_components'].update(rush_attempt=12,rush_yards_gained=50,rush_touchdown=0,rush_two_point_conv=0)
        r['expected_components'].update(rush_yards_gained=65,rush_touchdown=.5,rush_two_point_conv=0)
        r['workload'].update(carries=12,rushing_yards=50)
    result=freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['channels']['rushing']
    assert result['actual_average']==5
    assert result['challenger']==pytest.approx(9.5)
    record['history'][0]['season']=2025
    assert freeze_expected_opportunity(a,p,frozen_at=NOW)['rows'][0]['channels']=={}
