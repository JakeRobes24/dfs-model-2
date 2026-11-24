from datetime import date, timedelta

import pandas as pd
import pytest

from opportunity_evidence import opportunity_evidence
from slate_research import rotation_box_details


def test_box_participation_requires_evidence_and_rejects_name_collision():
    def player(name, person_id, minutes=None, comment=''):
        return {'firstName': name, 'personId': person_id, 'statistics': {'minutes': minutes},
                'comment': comment}

    played, absent = rotation_box_details(
        [player('Played', 1, '32:00'), player('Explicit', 2, comment='DNP - Injury'),
         player('Unknown', 3), player('Collision', 4, '12:00')],
        [player('Collision', 5), player('Inactive', 6)],
    )
    assert played == {'played'}
    assert absent == {'explicit', 'inactive'}


def test_rotation_splits_exclude_unknown_games_and_shrink_small_comparisons():
    slate = date(2026, 11, 20)
    pool = pd.DataFrame([
        dict(team='BOS', fanduel_id='1', fanduel_name='Rotation Player', prelock_status='', eligible=True),
        dict(team='BOS', fanduel_id='2', fanduel_name='Injured Teammate', prelock_status='out', eligible=False),
    ])
    logs = [
        dict(team='BOS', player='Rotation Player', nba_id='123', game_date=slate - timedelta(days=age),
             minutes=minutes, started=True, source='NBA box', points=10, reboundsTotal=5,
             assists=2, steals=1, blocks=0, turnovers=1,
             teammates_played=('injuredteammate',) if age == 1 else (),
             teammates_absent=('injuredteammate',) if age == 2 else ())
        for age, minutes in [(0, 48), (1, 20), (2, 32), (3, 24), (4, 24), (5, 25)]
    ]
    rotations, splits = opportunity_evidence(pool, logs, slate)
    assert rotations.loc[0, 'Games observed'] == 5
    assert rotations.loc[0, 'Last 5 minutes'] == 25
    assert rotations.loc[0, 'Last 10 minutes'] is None
    assert rotations.loc[0, 'FD points per minute'] == pytest.approx(105 / 125)
    assert splits.loc[0, 'Games with teammate'] == splits.loc[0, 'Games without teammate'] == 1
    assert splits.loc[0, 'Minutes gap (shrunk)'] == 2
    assert splits.loc[0, 'Evidence'] == 'Small sample'


def test_absence_rate_evidence_uses_complete_stats_and_excludes_conflicting_participation():
    from opportunity_evidence import rate_comparison, FD_WEIGHTS, OPPORTUNITY_WEIGHTS
    def game(minutes, points, complete=True):
        return dict(minutes=minutes, points=points, reboundsTotal=0, assists=0,
                    steals=0, blocks=0, turnovers=0,
                    fieldGoalsAttempted=10 if complete else None, freeThrowsAttempted=0)
    present = [game(20, 20), game(30, 30), game(20, 20)]
    absent = [game(20, 30), game(30, 45), game(20, 30, False)]
    fd = rate_comparison(present, absent, FD_WEIGHTS)
    assert fd['sufficient']
    assert fd['gap'] == pytest.approx(.5)
    assert fd['shrunk_gap'] == pytest.approx(.5 * 3 / 8)
    opp = rate_comparison(present, absent, OPPORTUNITY_WEIGHTS)
    assert not opp['sufficient']
    assert opp['without_games'] == 2 and opp['without_minutes'] == 50
    assert rate_comparison([], absent, FD_WEIGHTS)['gap'] is None

    slate = date(2026, 11, 20)
    pool = pd.DataFrame([
        dict(team='BOS', fanduel_id='1', fanduel_name='Player A', prelock_status='', eligible=True),
        dict(team='BOS', fanduel_id='2', fanduel_name='Player B', prelock_status='out', eligible=False),
    ])
    logs = [dict(game(30, 30), team='BOS', player='Player A', nba_id='1',
                 game_date=slate-timedelta(days=i), started=True, source='NBA box',
                 teammates_played=('playerb',) if i != 2 else (),
                 teammates_absent=('playerb',) if i != 1 else ())
            for i in (1, 2, 3)]
    _, splits = opportunity_evidence(pool, logs, slate)
    assert splits.loc[0, 'Games with teammate'] == 1
    assert splits.loc[0, 'Games without teammate'] == 1
    assert splits.loc[0, 'Complete FD games with'] == 1
    assert splits.loc[0, 'FD rate evidence'] == 'Small or incomplete sample'


def test_role_comparison_excludes_unknown_starter_status():
    slate = date(2026, 11, 20)
    pool = pd.DataFrame([dict(team='BOS', fanduel_id='1', fanduel_name='Player A',
                              prelock_status='', eligible=True)])
    logs = [dict(team='BOS', player='Player A', nba_id='1',
                 game_date=slate-timedelta(days=i), started=role, source='NBA box',
                 minutes=minutes, points=points, reboundsTotal=0, assists=0,
                 steals=0, blocks=0, turnovers=0, fieldGoalsAttempted=10, freeThrowsAttempted=0)
            for i, (role, minutes, points) in enumerate(
                [(True, 30, 45), (False, 20, 20), (None, 40, 100)], start=1)]
    summary, _ = opportunity_evidence(pool, logs, slate)
    row = summary.iloc[0]
    assert row['Games observed'] == 3
    assert row['Games with starter status'] == 2
    assert row['Minutes as starter'] == 30 and row['Minutes off bench'] == 20
    assert row['FD/min as starter'] == 1.5 and row['FD/min off bench'] == 1
    assert row['Starter complete FD games'] == row['Bench complete FD games'] == 1
    assert row['Starter/bench FD rate evidence'] == 'Small or incomplete sample'
