"""Exercise the default two-file workflow with controlled sources."""
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from model import SLOTS, allowed_slots
from slate_import import reconcile_exports
from slate_research import ET, RW_MINUTES, historical_context, score_slate

ROOT = Path(__file__).resolve().parent
AS_OF = datetime(2026, 11, 22, 16, tzinfo=ET)


def uploads():
    with (ROOT / 'nov20_reconciled_example.csv').open() as file:
        base = pd.read_csv(file).head(55)
    # Test CSV shape only. Assign the fixture to one synthetic matchup.
    contest = base.assign(game='BOS@NYK', team='BOS').rename(columns={
        'fanduel_id': 'Id', 'fanduel_name': 'Nickname', 'salary': 'Salary', 'team': 'Team',
        'game': 'Game', 'position': 'Position', 'roster_eligibility': 'Roster Position',
        'injury_flag': 'Injury Indicator',
    })
    daily = base.assign(team='Boston Celtics', gameInfo='BOS @ NYK').rename(columns={
        'fanduel_name': 'player', 'projected_minutes': 'minutes', 'projected_fd_points': 'fantasy',
    })
    return contest, daily


def test_contest_authority_and_ambiguous_projection_matches():
    contest, daily = uploads()
    daily = pd.concat([daily, daily.iloc[:1]], ignore_index=True)
    daily.loc[2, 'team'] = 'Knicks'
    manual_extra = daily.iloc[[3]].assign(gameInfo='IND @ ATL')
    daily = pd.concat([daily, manual_extra], ignore_index=True)
    raw = ('FanDuel lineup template\n' + contest.to_csv(index=False)).encode()
    pool, ident, extras = reconcile_exports(raw, daily.to_csv(index=False).encode())
    assert ident == '136961' and len(pool) == len(contest)
    assert extras == 2
    assert pool.iloc[0].identity_match == 'ambiguous'
    assert pool.iloc[2].identity_match == 'unmatched'
    assert pd.isna(pool.iloc[0].projected_fd_points) and pd.isna(pool.iloc[2].projected_fd_points)
    assert pool.salary.tolist() == contest.Salary.tolist()
    with pytest.raises(ValueError, match='mixes FanDuel contest IDs'):
        mixed = contest.copy()
        mixed.loc[0, 'Id'] = '123456-84680'
        reconcile_exports(mixed.to_csv(index=False).encode(), daily.to_csv(index=False).encode())


def test_history_filters_same_day_and_conflicting_player_keys():
    contest, daily = uploads()
    pool, _, _ = reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())
    player = pool.iloc[0]
    suffix = player.fanduel_id.split('-')[1]
    archive = pd.DataFrame([
        dict(slate_date='2026-11-20', name=player.fanduel_name, fanduel_id='111-' + suffix,
             actual_minutes=28),
        dict(slate_date='2026-11-22', name=player.fanduel_name, fanduel_id='222-' + suffix,
             actual_minutes=46),
    ])
    history = historical_context(pool, archive, [], AS_OF.date())
    assert history.iloc[0].recent_mpg == 28 and history.iloc[0].history_games == 1
    conflict = archive.iloc[[0]].assign(name='Different Person', fanduel_id='333-' + suffix)
    assert historical_context(pool, pd.concat([archive, conflict]), [], AS_OF.date()).empty


def test_corroborated_adjustment_flows_to_points_and_injury_takes_precedence():
    contest, daily = uploads()
    pool, _, _ = reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())
    player = pool.iloc[0]
    history = pd.DataFrame([dict(player=player.fanduel_name, recent_mpg=player.projected_minutes + 3,
                                 history_games=3)])
    estimate = dict(fanduel_id=player.fanduel_id, source=RW_MINUTES, independent_group='rotowire',
                    observed_at=AS_OF.isoformat(), official=False, status='', starter='', role='',
                    minutes=player.projected_minutes + 3)
    result, _ = score_slate(pool, history, [estimate], [], AS_OF)
    assert result.iloc[0].adjusted_minutes == pytest.approx(player.projected_minutes + 1)
    assert result.iloc[0].adjusted_fd_points > player.projected_fd_points
    injury = dict(estimate, source='NBA', official=True, status='out', minutes=None)
    result, audit = score_slate(pool, history, [estimate, injury], [], AS_OF)
    assert not result.iloc[0].eligible and result.iloc[0].adjusted_fd_points == 0
    assert audit.review.eq('Reviewed').all()


def test_default_streamlit_workflow_generates_four_legal_candidates():
    contest, daily = uploads()
    with (patch('site_ui.public_research', return_value=([], [], [('NBA injury report', 'Unavailable')])),
          patch('site_ui.public_rotations', return_value=([], 'Unavailable'))):
        app = AppTest.from_file(str(ROOT / 'app_staging.py'), default_timeout=45).run()
        assert app.radio(key='site_view').value == 'Build a slate'
        assert not any('November 20' in item.value for item in app.subheader)
        app.file_uploader(key='slate_contest').upload(
            'test.csv', contest.to_csv(index=False).encode(), 'text/csv').run()
        app.file_uploader(key='slate_daily').upload(
            'DAILY.csv', daily.to_csv(index=False).encode(), 'text/csv').run()
        assert not app.exception and not app.error
        app.button(key='slate_optimize').click().run()
        assert not app.exception and not app.error
        _, (lineups, comparison, alternative) = app.session_state['slate_results']
        assert len(comparison) == 4 and len(alternative) == 9
        for _, lineup in lineups.groupby('lineup'):
            assert Counter(lineup.slot) == Counter(SLOTS)
            assert lineup.fanduel_id.nunique() == 9 and lineup.salary.sum() <= 60000
            for row in lineup.itertuples():
                eligibility = contest.loc[contest.Id.eq(row.fanduel_id), 'Roster Position'].iat[0]
                assert row.slot in allowed_slots(eligibility)
        assert set(alternative.fanduel_id) != set(lineups[lineups.lineup.eq(1)].fanduel_id)


def test_rotogrinders_accepts_dated_upcoming_rows_only(monkeypatch):
    from datetime import datetime
    from slate_research import ET, rotogrinders_research

    response = b"""
    <span><b>FPTS Updated</b><span data-role="localtime" data-value="2026-11-22T00:41:25Z"></span></span>
    <span data-field="schedule" data-value="1">2026-11-21 10:00pm (BOS @ SAC)</span>
    <span data-field="schedule" data-value="2">2026-11-21 1:00pm (BOS @ SAC)</span>
    <table><thead><tr><th>PLAYER</th><th>TEAM</th><th>OPP</th><th>MINUTES</th>
    <th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TO</th></tr></thead><tbody>
    <tr data-schedule="1"><td><a data-role="modal">Sample Player</a></td>
    <td>BOS</td><td>SAC</td><td>30</td><td>10</td><td>5</td><td>3</td><td>1</td><td>1</td><td>2</td></tr>
    <tr data-schedule="2"><td><a data-role="modal">Already Started</a></td>
    <td>BOS</td><td>SAC</td><td>30</td><td>10</td><td>5</td><td>3</td><td>1</td><td>1</td><td>2</td></tr>
    </tbody></table>"""
    monkeypatch.setattr('slate_research.fetch', lambda url: response)
    now = datetime(2026, 11, 21, 19, 50, tzinfo=ET)
    (notes, projections), _ = rotogrinders_research(now.date(), now)
    assert [row['player'] for row in notes] == ['Sample Player']
    assert notes[0]['minutes'] == 30
    assert projections[0]['points'] == 24.5
