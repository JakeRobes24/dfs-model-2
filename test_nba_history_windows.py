from datetime import date,timedelta
import pytest
from nba_history_windows import compare_history_windows

def sample():
    return [dict(nba_id='101',team='BOS',game='BOS@NYK',
                 source='https://www.nba.com/game/bos-vs-nyk/box-score',
                 game_date=(date(2026,11,1)+timedelta(days=i)).isoformat(),
                 minutes=25+i,points=12+i,reboundsTotal=5,assists=4,steals=1,blocks=0,
                 turnovers=2,fieldGoalsAttempted=10+i,freeThrowsAttempted=4)
            for i in range(14)]

def run(rows):
    return compare_history_windows(rows,cutoff_day='2026-11-26')

def test_equal_support_within_each_cohort_and_no_future_dates():
    r=run(sample())
    assert not r['certified']
    assert {x['player_games'] for x in r['summary'] if x['cohort']==8}=={6}
    assert {x['player_games'] for x in r['summary'] if x['cohort']==12}=={2}
    assert all(max(x['training_dates'])<x['date'] for x in r['rows'])
    assert len({x['policy'] for x in r['summary'] if x['cohort']==8})==5
    assert len({x['policy'] for x in r['summary'] if x['cohort']==12})==8

def test_four_game_baseline_and_same_target_hybrid():
    r=[x for x in run(sample())['rows'] if x['cohort']==8 and x['date']=='2026-11-09']
    p={x['policy']:x for x in r}
    expected=sum(12+i+1.2*5+1.5*4+3-2 for i in range(4,8))/4
    assert p['equal_4']['predicted_fd']==pytest.approx(expected)
    assert p['minutes4_rate8']['minutes_abs_error']==pytest.approx(p['equal_4']['minutes_abs_error'])
    assert p['minutes4_rate8']['efficiency_abs_error']==pytest.approx(p['equal_8']['efficiency_abs_error'])

def test_target_results_do_not_change_target_forecasts():
    f=sample()
    a=run(f)
    f[-1]['points']=100
    b=run(f)
    assert [x['predicted_fd'] for x in a['rows']]==[x['predicted_fd'] for x in b['rows']]

def test_incomplete_window_cannot_skip_missing_game():
    f=sample()
    f[7].pop('assists')
    assert not run(f)['rows']

def test_no_cross_team_or_duplicate_date_history():
    f=sample()
    f[-1]['team']='NYK'
    assert all(x['date']!='2026-11-14' for x in run(f)['rows'])
    assert not run(sample()+[dict(sample()[7])])['rows']

def test_future_records_never_enter_prior():
    f=sample()
    assert run(f)['rows']==run(f+[dict(f[-1],game_date='2026-11-26')])['rows']
