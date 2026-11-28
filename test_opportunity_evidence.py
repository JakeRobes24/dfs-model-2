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


def test_role_matched_absence_distinguishes_role_mix_from_within_role_effect():
    from opportunity_evidence import role_matched_absence
    def log(role, minutes):
        return dict(started=role, minutes=minutes, points=minutes, reboundsTotal=0,
                    assists=0, steals=0, blocks=0, turnovers=0,
                    fieldGoalsAttempted=10, freeThrowsAttempted=0)
    present = [log(False, 18)] * 4 + [log(True, 34)]
    absent = [log(False, 18)] + [log(True, 34)] * 4 + [log(None, 45)]
    report = role_matched_absence(present, absent)
    assert report['Role-matched strata'] == 2
    assert report['Role-matched games per side'] == 2
    assert report['Role-matched minutes gap'] == 0
    assert report['Role-matched FD/min gap'] == 0
    assert report['Role-matched evidence'] == 'Small sample'
    missing = role_matched_absence([log(True, 32)], [log(False, 18)])
    assert missing['Role-matched minutes gap'] is None
    assert missing['Role-matched evidence'] == 'No overlapping known roles'


def test_current_multiple_absences_do_not_masquerade_as_isolated_history():
    slate = date(2026, 11, 25)
    pool = pd.DataFrame([
        dict(team='BOS', fanduel_id='1', fanduel_name='Player A', prelock_status='', eligible=True),
        dict(team='BOS', fanduel_id='2', fanduel_name='Player B', prelock_status='out', eligible=False),
        dict(team='BOS', fanduel_id='3', fanduel_name='Player C', prelock_status='inactive', eligible=False)])
    def log(age, played, absent, minutes):
        return dict(team='BOS', player='Player A', nba_id='1', game_date=slate-timedelta(days=age),
                    started=True, source='NBA box', minutes=minutes, points=minutes, reboundsTotal=0,
                    assists=0, steals=0, blocks=0, turnovers=0,
                    fieldGoalsAttempted=10, freeThrowsAttempted=0,
                    teammates_played=played, teammates_absent=absent)
    logs = [log(1, ('playerb','playerc'), (), 20),
            log(2, ('playerc',), ('playerb',), 24),
            log(3, (), ('playerb','playerc'), 40),
            log(4, (), ('playerb',), 45)]
    _, splits = opportunity_evidence(pool, logs, slate)
    b = splits.set_index('Out teammate').loc['Player B']
    assert b['Games without teammate'] == 3
    assert b['Other currently out teammates'] == 1
    assert b['Isolated games with teammate'] == b['Isolated games without teammate'] == 1
    assert b['Isolated role-matched games per side'] == 1
    assert b['Isolated role-matched minutes gap (shrunk)'] == pytest.approx(4/6)
    assert b['Isolated role-matched FD/min gap'] == 0
    assert 'Player C' in splits['Out teammate'].tolist()


def test_rate_evidence_ignores_zero_missing_or_nonfinite_minutes():
    from opportunity_evidence import stat_rate, FD_WEIGHTS
    row = dict(minutes=20, points=20, reboundsTotal=0, assists=0, steals=0, blocks=0, turnovers=0)
    invalid = [dict(row, minutes=m) for m in (0, None, float('inf'), float('nan'))]
    assert stat_rate(invalid, FD_WEIGHTS) is None
    assert stat_rate([row, *invalid], FD_WEIGHTS) == 1


def test_component_evidence_requires_joint_complete_stat_games():
    from opportunity_evidence import component_rate_evidence
    row=dict(minutes=30,points=20,turnovers=2,reboundsTotal=5,assists=4,
             steals=1,blocks=0,fieldGoalsAttempted=12,freeThrowsAttempted=4)
    ev=component_rate_evidence([row,row,dict(row,fieldGoalsAttempted=None)])
    assert ev['games']==2
    assert ev['minutes']==60
    assert ev['opportunities_per_minute']==pytest.approx(15.76/30)
    assert ev['net_per_opportunity']==pytest.approx(18/15.76)
    assert ev['peripheral_per_minute']==pytest.approx(15/30)
    assert component_rate_evidence([dict(row,blocks=None)])['net_per_opportunity'] is None
