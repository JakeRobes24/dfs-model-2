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
    assert len(details) == 21
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


def test_combined_policy_frozen_sources_and_date_separation():
    import json
    from nba_combined_scoring_shadow import COMBINED_POLICY
    a = replay(date(2026,11,24), 1, 2, 39)
    b = replay(date(2026,11,25), 2, 2, 39)
    def add_sources(frame):
        stamp = frame.slate_date.iloc[0]
        notes = [dict(family='a', points=36., weight=1., paired_minutes=30.,
                      observed_at=stamp+'T19:00:00Z'),
                 dict(family='b', points=40., weight=1., paired_minutes=None,
                      observed_at=stamp+'T19:30:00Z')]
        frame = frame.assign(injury_flag='', prelock_status='',
            minutes_method='prelock_independent_consensus',
            blend_status='Minutes/status adjustment takes priority',
            adjusted_fd_points=42., independent_fd_points=38.,
            projection_source_count=2, projection_source_spread=4.,
            projection_sources_json=json.dumps(notes))
        late = [dict(x, observed_at=stamp+'T20:01:00Z') for x in notes]
        frame.loc[frame.index[1], 'projection_sources_json'] = json.dumps(late)
        return frame
    _, result = compare_across_slates(pd.concat([add_sources(a),add_sources(b)], ignore_index=True))
    rows = result.loc[result.Policy.eq(COMBINED_POLICY)].set_index('Period')
    assert rows['Paired players'].to_dict() == {'Exploratory': 1, 'Prospective': 1}
    assert rows.loc['Prospective','Reviewed MAE (player weighted)'] == pytest.approx(3.)
    assert rows.loc['Prospective','Shadow MAE (player weighted)'] == pytest.approx(1.4)
    assert rows.loc['Prospective','Review status'] == 'Insufficient prospective evidence'
    _, unsupported = compare_across_slates(b)
    assert unsupported.loc[unsupported.Policy.eq(COMBINED_POLICY),'Paired players'].iloc[0] == 0


def test_paired_rate_policy_has_own_prospective_start():
    from nba_combined_scoring_shadow import PAIRED_RATE_POLICY
    frames = [replay(date(2026,11,25), 1, 2, 39), replay(date(2026,11,26), 2, 2, 39)]
    _, result = compare_across_slates(pd.concat(frames,ignore_index=True))
    rows = result.loc[result.Policy.eq(PAIRED_RATE_POLICY)].set_index('Period')
    assert set(rows.index) == {'Exploratory','Prospective'}
    assert rows['Paired players'].eq(0).all()
