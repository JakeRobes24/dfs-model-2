from datetime import date, timedelta
import pandas as pd
import pytest
from nba_shadow_research import FEATURES
from nba_shadow_multislate import compare_across_slates


def replay(day, contest, n, actual):
    stamp = day.isoformat()
    rows = pd.DataFrame({'fanduel_id': [f'{contest}-{i}' for i in range(n)],
        'slate_date': stamp, 'replay_captured_at_utc': stamp+'T20:00:00Z',
        'replay_cutoff_utc': stamp+'T23:00:00Z', 'replay_before_full_slate_tip': True,
        'replay_timing': 'before_scheduled_tip', 'eligible': True, 'verified_outcome': 'played',
        'daily_points': 30, 'adjusted_fd_points': 30, 'adjusted_minutes': 30,
        'actual_points': actual, 'nba_source': 'NBA box'})
    for field in FEATURES:
        rows[field] = None
    return rows.assign(shadow_recent_fppm=2, shadow_recent_games=3, shadow_recent_minutes=90)


def test_date_weighting_prospective_separation_and_minimum_evidence():
    a = replay(date(2026,11,24), 1, 10, 36)
    b = replay(date(2026,11,25), 2, 100, 36)
    c = replay(date(2026,11,26), 3, 10, 30)
    details, result = compare_across_slates(pd.concat([a,b,c], ignore_index=True))
    recent = result.loc[result.Policy.eq('Recent rate')].set_index('Period')
    assert recent.loc['Exploratory','Paired players'] == 10
    assert recent.loc['Prospective','Paired players'] == 110
    assert recent.loc['Prospective','Improvement (player weighted)'] == pytest.approx(540/110)
    assert recent.loc['Prospective','Improvement (equal date weight)'] == 0
    assert recent.loc['Prospective','Review status'] == 'Insufficient prospective evidence'
    assert recent.loc['Prospective','Improved dates'] == 1
    assert len(details) == 15
    more = pd.concat([replay(date(2026,11,25)+timedelta(days=i),i+10,20,36)
                      for i in range(5)], ignore_index=True)
    _, result = compare_across_slates(more)
    row = result.loc[result.Policy.eq('Recent rate')].iloc[0]
    assert row['Review status'] == 'Needs independent validation'
    assert row['Paired players'] == 100
    assert result.loc[result.Policy.eq('Pace'),'Paired players'].iloc[0] == 0


def test_duplicate_contests_and_invalid_timing_fail_closed():
    a = replay(date(2026,11,25), 1, 2, 36)
    for bad in [pd.concat([a,a]), pd.concat([a,a.assign(fanduel_id=['2-0','2-1'])]),
                a.assign(replay_captured_at_utc='2026-11-25T23:01:00Z'),
                a.assign(replay_before_full_slate_tip=False)]:
        with pytest.raises(ValueError, match='verified full-slate'):
            compare_across_slates(bad)
    _, result = compare_across_slates(a.drop(columns=list(FEATURES)))
    assert result['Paired players'].eq(0).all()
