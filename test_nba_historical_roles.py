import pytest
from nba_historical_roles import official_roles,espn_roles,enrich_roles,flag,minutes

def official():
    def club(t,base):
        return dict(teamTricode=t,players=[dict(personId=base+i,starter=str(int(i<5)),
            statistics={'minutes':'PT30M00.00S'}) for i in range(6)])
    return dict(gameId='0022600001',gameStatus=3,awayTeam=club('BOS',100),homeTeam=club('NYK',200))

def rows():
    return [dict(team=t,nba_id=str(b+i),player=f'Player {b+i}',minutes=30,started=None)
            for t,b in [('BOS',100),('NYK',200)] for i in range(6)]

def test_exact_official_roles_and_source_without_mutation():
    original=rows()
    roles=official_roles(official(),'0022600001','BOS','NYK')
    out=enrich_roles(original,roles,source='NBA liveData')
    assert sum(r['started'] is True for r in out)==10
    assert sum(r['started'] is False for r in out)==2
    assert all(r['started'] is None for r in original)
    assert all(r['historical_role_source']=='NBA liveData' for r in out)

def test_invalid_missing_flag_and_wrong_game_rejected():
    g=official()
    g['awayTeam']['players'][0].pop('starter')
    with pytest.raises(ValueError):official_roles(g,'0022600001','BOS','NYK')
    with pytest.raises(ValueError):official_roles(official(),'0022600002','BOS','NYK')

def test_mismatched_minutes_or_identity_preserve_unknown():
    r=rows()
    r[0]['minutes']=20
    out=enrich_roles(r,official_roles(official(),'0022600001','BOS','NYK'),source='NBA')
    assert all(x['started'] is None for x in out[:6])
    assert sum(x['started'] is True for x in out[6:])==5
    r=rows()
    r[0]['nba_id']='999'
    assert all(x['started'] is None for x in enrich_roles(r,official_roles(official(),'0022600001','BOS','NYK'),source='NBA')[:6])

def test_conflict_with_explicit_role_rejects_team():
    r=rows()
    r[0]['started']=False
    out=enrich_roles(r,official_roles(official(),'0022600001','BOS','NYK'),source='NBA')
    assert out[0]['started'] is False and out[1]['started'] is None

def test_espn_exact_secondary_role_match():
    def side(t,b):
        return dict(team={'abbreviation':t},statistics=[dict(labels=['MIN'],athletes=[
            dict(athlete={'displayName':f'Player {b+i}'},starter=i<5,stats=['30']) for i in range(6)])])
    data=dict(header=dict(id='42',competitions=[dict(status={'type':{'completed':True}},
        competitors=[dict(homeAway='away',team={'abbreviation':'BOS'}),
                     dict(homeAway='home',team={'abbreviation':'NYK'})])]),
        boxscore=dict(players=[side('BOS',100),side('NYK',200)]))
    roles=espn_roles(data,'42','BOS','NYK')
    out=enrich_roles(rows(),roles,source='ESPN',by_name=True)
    assert sum(r['started'] is True for r in out)==10
    data['boxscore']['players'][0]['statistics'][0]['athletes'][0].pop('starter')
    with pytest.raises(ValueError):espn_roles(data,'42','BOS','NYK')

def test_explicit_flag_and_minutes_parsing():
    assert flag('1') is True and flag('0') is False
    assert flag('false') is None and flag(None) is None
    assert minutes('PT32M30.00S')==32.5
    assert minutes('32:30')==32.5
    assert minutes('32')==32
    assert minutes('32:90') is None


def test_role_recovery_exact_schedule_and_source():
    from datetime import date
    from nba_historical_roles import recover_espn_roles
    day=date(2026,11,24)
    f=[dict(r,game_date=day,game='BOS@NYK') for r in rows()]
    event=dict(id='42',date='2026-11-25T01:00:00Z',competitions=[dict(
        status={'type':{'completed':True}},competitors=[
            dict(homeAway='away',team={'abbreviation':'BOS'}),
            dict(homeAway='home',team={'abbreviation':'NYK'})])])
    def side(t,b):
        return dict(team={'abbreviation':t},statistics=[dict(labels=['MIN'],athletes=[
            dict(athlete={'displayName':f'Player {b+i}'},starter=i<5,stats=['30']) for i in range(6)])])
    summary=dict(header=dict(id='42',competitions=event['competitions']),
                 boxscore=dict(players=[side('BOS',100),side('NYK',200)]))
    def load(url):
        return {'events':[event]} if 'scoreboard?' in url else summary
    out,report=recover_espn_roles(f,cutoff_day=date(2026,11,26),load_json=load)
    assert report['known']==12 and report['attempted_games']==1
    assert sum(r['started'] is True for r in out)==10
    assert all(r['started'] is None for r in f)
    assert all(r['historical_role_source'].endswith('event=42') for r in out)
    event['date']='2026-11-24T01:00:00Z'
    out,report=recover_espn_roles(f,cutoff_day=date(2026,11,26),load_json=load)
    assert report['known']==0 and report['statuses']['unmatched or ambiguous event']==1

def test_role_recovery_source_unavailable_is_bounded():
    from datetime import date,timedelta
    from nba_historical_roles import recover_espn_roles
    day=date(2026,11,24)
    f=[dict(r,game_date=day-timedelta(days=i),game='BOS@NYK') for i in range(6) for r in rows()]
    def load(url):
        raise OSError('not available')
    out,report=recover_espn_roles(f,cutoff_day=date(2026,11,26),load_json=load,max_games=4)
    assert report['known']==0 and report['attempted_games']==3
    assert report['statuses']['not attempted']==3 and len(out)==len(f)

def test_secondary_role_source_survives_opportunity_summary():
    from opportunity_evidence import box_sources
    assert box_sources([{'source':'NBA box','historical_role_source':'ESPN final box'}])=='ESPN final box · NBA box'
