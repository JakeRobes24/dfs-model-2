import json
from pathlib import Path
from copy import deepcopy
import pytest
from nfl_role_window_review import compare_backfield_windows

def fixture():
    return json.loads((Path(__file__).parent/'docs/validation/nov25-role-window.json').read_text())
def run(f):
    return compare_backfield_windows(f['history'],player_ids=f['player_ids'],team=f['team'],target_day=f['target_day'])

def test_verified_archive_windows():
    f=fixture()
    r=run(f)
    e=f['expected']
    assert r['supported'] and r['games_available']==8
    assert r['recent']['first_player_share']==pytest.approx(e['recent_share'])
    assert r['prior']['first_player_share']==pytest.approx(e['prior_share'])
    assert r['share_change_pp']==pytest.approx(e['share_change_pp'])
    assert r['volume_change_pct']==pytest.approx(e['volume_change_pct'])
    assert r['share_review'] and r['volume_review']
    assert not r['certified']
    assert not set(r['prior']['dates']) & set(r['recent']['dates'])

def test_future_target_and_other_team_never_used():
    f=fixture()
    original=run(f)
    for day,team in [('2026-11-25','LAR'),('2026-12-01','LAR'),('2026-11-20','KC')]:
        f['history'].append(dict(f['history'][0],date=day,team=team))
    assert run(f)==original

def test_insufficient_history_not_negative_signal():
    f=fixture()
    f['history']=f['history'][1:]
    r=run(f)
    assert not r['supported']
    assert 'share_review' not in r

@pytest.mark.parametrize('change', ['duplicate','missing','negative','fractional','zero_pair','missing_source'])
def test_invalid_history_rejected(change):
    f=fixture()
    row=f['history'][0]
    pid=f['player_ids'][0]
    if change=='duplicate':f['history'].append(deepcopy(row))
    elif change=='missing':row['carries'].pop(pid)
    elif change=='negative':row['carries'][pid]=-1
    elif change=='fractional':row['carries'][pid]=1.5
    elif change=='zero_pair':row['carries']=dict.fromkeys(f['player_ids'],0)
    else:row['source']=''
    with pytest.raises(ValueError):run(f)
