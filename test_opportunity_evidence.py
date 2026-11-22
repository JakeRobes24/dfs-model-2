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
