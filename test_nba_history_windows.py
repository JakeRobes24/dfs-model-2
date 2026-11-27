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


def test_short_long_challenge_changes_minutes_only_on_identical_rows():
    result = compare_history_windows(sample(), cutoff_day='2026-11-26', short_long_challenge=True)
    distinct = {row['policy']: row for row in result['rows']
                if row['cohort'] == 8 and row['date'] == '2026-11-09'}
    long = distinct['equal_8']
    short = distinct['minutes3_long_rate']
    blend = distinct['minutes3_long_blend']
    assert short['efficiency_abs_error'] == blend['efficiency_abs_error'] == long['efficiency_abs_error']
    assert short['minutes_abs_error'] < blend['minutes_abs_error'] < long['minutes_abs_error']
    assert blend['predicted_fd'] == pytest.approx((long['predicted_fd'] + short['predicted_fd']) / 2)


def test_component_challengers_change_one_rate_and_preserve_support():
    rows = compare_history_windows(sample(), cutoff_day='2026-11-26', component_challenge=True)['rows']
    selected = {r['policy']: r for r in rows if r['cohort']==8 and r['date']=='2026-11-14'}
    baseline = selected['equal_8']
    for field, metric in [('opportunity','opportunity_abs_error'), ('efficiency','efficiency_abs_error'), ('peripherals','peripheral_abs_error')]:
        for prefix in ('blend','recent'):
            challenger = selected[f'{prefix}_{field}']
            assert challenger['predicted_minutes'] == baseline['predicted_minutes']
            for other in ('opportunity_abs_error','efficiency_abs_error','peripheral_abs_error'):
                if other != metric:
                    assert challenger[other] == baseline[other]
    from collections import Counter
    assert set(Counter(r['policy'] for r in rows if r['cohort']==8).values()) == {6}
    changed = sample()
    changed[-1]['points'] = 100
    replay = compare_history_windows(changed, cutoff_day='2026-11-26', component_challenge=True)['rows']
    assert [r['predicted_fd'] for r in rows] == [r['predicted_fd'] for r in replay]


def test_rate_challenge_preserves_minutes_and_decomposes_point_error():
    result = compare_history_windows(sample(), cutoff_day='2026-11-26', rate_challenge=True)
    rows = result['rows']
    for row in rows:
        assert row['minutes_effect'] + row['rate_effect'] == pytest.approx(row['fd_bias'])
        assert row['predicted_fppm'] * row['predicted_minutes'] == pytest.approx(row['predicted_fd'])
    for cohort in (8, 12):
        chosen = {r['policy']: r for r in rows if r['cohort']==cohort and r['date']=='2026-11-14'}
        blend = chosen['long_minutes_blended_rate']
        long = chosen[f'equal_{cohort}']
        short = chosen['equal_4']
        assert blend['predicted_minutes'] == long['predicted_minutes']
        assert blend['predicted_fppm'] == pytest.approx((long['predicted_fppm']+short['predicted_fppm'])/2)
        assert blend['fppm_abs_error'] == pytest.approx(abs(blend['fppm_bias']))
    changed = sample()
    changed[-1]['points'] = 100
    replay = compare_history_windows(changed, cutoff_day='2026-11-26', rate_challenge=True)
    assert [r['predicted_fd'] for r in rows] == [r['predicted_fd'] for r in replay['rows']]
