import json
from pathlib import Path
import pytest
from nfl_history_baseline_review import compare_history_baselines, compare_split_workload_baselines

ROOT=Path(__file__).parent/'docs/validation'

def test_split_grid_matches_archived_arithmetic_and_original_baselines():
    f=json.loads((ROOT/'nfl-multi-backfield-baselines.json').read_text())
    expected=json.loads((ROOT/'nfl-split-workload-benchmark.json').read_text())['results']
    actual=[]
    for c in f['cohorts']:
        kw={k:c[k] for k in ('history','player_ids','team','target_day')}
        r=compare_split_workload_baselines(**kw)
        original=compare_history_baselines(**kw)
        assert len(r['rows'])==9*(len(c['history'])-4)
        assert not r['certified']
        for row in r['rows']:
            assert all(d<row['date'] for d in row['training_dates'])
            if row['volume']==row['share']:
                old=next(x for x in original['rows'] if x['date']==row['date'] and x['policy']==row['volume'])
                assert row['predicted_carries']==pytest.approx(old['predicted_carries'])
        actual.append(r['summary'])
    for e in expected:
        got=[next(x for x in a if x['volume']==e['volume'] and x['share']==e['share']) for a in actual]
        assert sum(a['mae'] for a in got)/len(got)==pytest.approx(e['equal_pair_mae'])
        assert max(a['worst'] for a in got)==pytest.approx(e['worst'])
        for a,b in zip(got,e['team']):
            assert a['dates']==b['dates']
            assert a['mae']==pytest.approx(b['mae'])
            assert a['worst']==pytest.approx(b['worst'])

def test_split_grid_excludes_target_date_and_does_not_use_heldout_workload():
    c=json.loads((ROOT/'nfl-multi-backfield-baselines.json').read_text())['cohorts'][0]
    kw={k:c[k] for k in ('history','player_ids','team','target_day')}
    original=compare_split_workload_baselines(**kw)
    kw['history'].append(dict(kw['history'][0],date=kw['target_day']))
    assert compare_split_workload_baselines(**kw)==original
    kw['history'][-2]['carries'][kw['player_ids'][0]]=1
    updated=compare_split_workload_baselines(**kw)
    assert [r['predicted_carries'] for r in updated['rows']]==[r['predicted_carries'] for r in original['rows']]
