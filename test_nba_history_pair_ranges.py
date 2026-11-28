from datetime import date,timedelta
import pytest
from nba_history_pair_ranges import compare_pair_ranges,_fit_dependence

def fixture():
    rows=[]
    for i in range(16):
        for g in range(5):
            away,home=f'T{g}A',f'T{g}B'
            for p in range(6):
                rows.append(dict(nba_id=str(g*6+p+1),team=away if p<3 else home,
                    game=f'{away}@{home}',source='https://www.nba.com/game/test/box-score',
                    game_date=(date(2026,11,1)+timedelta(days=i)).isoformat(),
                    minutes=25+(p+i)%10,points=12+(i*2+g+p)%17,reboundsTotal=5,
                    assists=4,steals=1,blocks=0,turnovers=2,
                    fieldGoalsAttempted=12+(p+i)%8,freeThrowsAttempted=4))
    return rows

def run(f):
    return compare_pair_ranges(f,cutoff_day='2026-11-26',draws=200)

def test_chronological_fit_and_identical_pairs():
    r=run(fixture())
    assert len(r['fits'])==3
    assert all(x['training_latest']<x['date'] for x in r['fits'])
    assert len(r['summary'])==4
    assert {x['games'] for x in r['summary']}=={15}
    assert {x['pairs'] for x in r['summary'] if x['relationship']=='teammate'}=={90}
    assert {x['pairs'] for x in r['summary'] if x['relationship']=='opponent'}=={135}
    assert not r['certified']
    assert all(abs(x['rho'])<=.35 for x in r['rows'])

def test_target_points_do_not_change_own_intervals():
    f=fixture()
    a=run(f)
    f[-1]['points']=100
    b=run(f)
    keys=('date','game','players','policy','rho','p10','p90')
    assert [[r[k] for k in keys] for r in a['rows']]==[[r[k] for k in keys] for r in b['rows']]

def test_repeatable_and_no_small_sample_fit():
    f=fixture()
    assert run(f)==run(f)
    assert not run(f[:12*30])['summary']
    assert _fit_dependence([], {}) is None

def test_invalid_draws():
    with pytest.raises(ValueError):compare_pair_ranges([],cutoff_day='2026-11-26',draws=0)
