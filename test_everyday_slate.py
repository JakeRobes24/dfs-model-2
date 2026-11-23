"""Exercise the default two-file workflow with controlled sources."""
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from model import SLOTS, allowed_slots, optimize_late_swap
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
    daily = daily.assign(points=20, rebounds=0, assists=-1)
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
    assert pd.isna(pool.iloc[0].daily_points) and pd.isna(pool.iloc[2].daily_points)
    assert pool.iloc[1].daily_points == 20 and pool.iloc[1].daily_rebounds == 0
    assert pd.isna(pool.iloc[1].daily_assists)
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
          patch('site_ui.public_rotations', return_value=([], 'Unavailable')),
          patch('site_ui.public_slate_schedule', return_value=[]) as schedule):
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
        schedule.return_value = [dict(awayTeam={'teamTricode': 'BOS'}, homeTeam={'teamTricode': 'NYK'},
                                      gameTimeUtc=datetime.now(ET).isoformat(), gameStatus=2)]
        app.run()
        assert not app.exception
        assert app.button(key='slate_optimize').disabled
        assert any('reached tip' in warning.value for warning in app.warning)
        assert any('Saved pre-tip candidates' in caption.value for caption in app.caption)


def test_contest_tip_checks_scope_date_and_early_start():
    from site_ui import started_contest_games

    game = dict(awayTeam={'teamTricode': 'BOS'}, homeTeam={'teamTricode': 'NYK'},
                gameTimeUtc='2026-11-22T22:00:00Z', gameStatus=1)
    wrong_day = dict(game, gameTimeUtc='2026-11-21T22:00:00Z')
    early = dict(game, actualStartTimeUTC='2026-11-22T20:59:00Z')
    assert started_contest_games([game], ['NYK@BOS'], AS_OF) == (set(), True)
    assert started_contest_games([wrong_day], ['NYK@BOS'], AS_OF) == (set(), False)
    assert started_contest_games([early], ['NYK@BOS'], AS_OF) == ({'BOS/NYK'}, True)
    assert started_contest_games([early], ['LAL@LAC'], AS_OF) == (set(), False)


def test_late_swap_preserves_second_util_and_ignores_other_closed_players():
    ids = [f'123-{i}' for i in range(11)]
    pool = pd.DataFrame({
        'fanduel_id': ids, 'fanduel_name': ids, 'eligible': True, 'salary': 6500,
        'roster_eligibility': 'PG/SG/SF/PF/G/F/F/C/UTIL/C', 'adjusted_minutes': 30,
        'adjusted_fd_points': [25] * 7 + [1, float('nan'), 50, 100],
        'confidence': 'high', 'minutes_method': 'DAILY', 'injury_flag': '',
    })
    pool.loc[8, 'eligible'] = False
    original = pd.DataFrame({'slot': SLOTS, 'fanduel_id': ids[:9]})
    result = optimize_late_swap(pool, original, [ids[8], ids[10]])
    assert result.slot.tolist() == SLOTS
    assert result.iloc[8].fanduel_id == ids[8] and result.iloc[8].locked
    assert pd.isna(result.iloc[8].adjusted_fd_points)
    assert ids[10] not in result.fanduel_id.values and ids[9] in result.fanduel_id.values
    assert ids[7] not in result.fanduel_id.values
    assert result.salary.sum() == 58500
    assert result.iloc[8].fd_points_delta == 0 and not result.iloc[8].changed
    assert result.fd_points_delta.sum() == 49
    with pytest.raises(ValueError, match='No legal late-swap'):
        optimize_late_swap(pool.assign(eligible=False), original, [ids[8], ids[10]])


def test_streamlit_late_swap_compares_entered_and_candidate_slots():
    contest, daily = uploads()
    contest.loc[:6, 'Game'] = 'BOS@CHI'
    daily.loc[:6, 'gameInfo'] = 'BOS @ CHI'
    with (patch('site_ui.public_research', return_value=([], [], [])),
          patch('site_ui.public_rotations', return_value=([], 'Unavailable')),
          patch('site_ui.public_slate_schedule', return_value=[]),
          patch('site_ui.started_contest_games', return_value=(set(), True)) as game_state):
        app = AppTest.from_file(str(ROOT / 'app_staging.py'), default_timeout=45).run()
        app.file_uploader(key='slate_contest').upload('contest.csv', contest.to_csv(index=False).encode(), 'text/csv')
        app.file_uploader(key='slate_daily').upload('DAILY.csv', daily.to_csv(index=False).encode(), 'text/csv').run()
        app.button(key='slate_optimize').click().run()
        lineups = app.session_state['slate_results'][1][0]
        entered = lineups.loc[lineups.lineup.eq(1), ['slot', 'fanduel_id']]
        game_state.return_value = ({'BOS/CHI'}, True)
        app.run()
        app.file_uploader(key='slate_late_swap').upload('entered.csv', entered.to_csv(index=False).encode(),
                                                      'text/csv').run()
        app.button(key='slate_late_swap_run').click().run()
        assert not app.exception and not app.error
        assert app.button(key='slate_optimize').disabled
        swap = app.session_state['late_swap_result'][1]
        locked = set(entered.fanduel_id) & set(contest.loc[:6, 'Id'])
        assert locked and set(swap.loc[swap.locked, 'fanduel_id']) == locked
        assert swap.loc[swap.locked, 'changed'].eq(False).all()
        assert any('Projected points change' in caption.value for caption in app.caption)
        assert any('UTIL 2' in frame.value.get('slot', []).tolist() for frame in app.dataframe if 'slot' in frame.value)


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


def test_weighted_blend_requires_agreement_and_yields_to_late_news():
    from datetime import timedelta
    from slate_research import DFF, PROPSIMS, LINEUPEXPERTS_TODAY

    contest, daily = uploads()
    pool, _, _ = reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())
    player = pool.iloc[0]
    baseline = player.projected_fd_points
    estimates = [dict(fanduel_id=player.fanduel_id, source=source, points=baseline + delta,
                      observed_at=(AS_OF - age).isoformat())
                 for source, delta, age in [(DFF, 1, timedelta(hours=3)), (PROPSIMS, 3, timedelta())]]
    result, _ = score_slate(pool, historical_context(pool, pd.DataFrame(), [], AS_OF.date()), [], estimates, AS_OF)
    assert result.iloc[0].adjusted_fd_points == pytest.approx(baseline + .4 * (0.5 + 3) / 1.5)
    reviewed = dict(estimates[1], source=LINEUPEXPERTS_TODAY, points=baseline + 2)
    result, _ = score_slate(pool, historical_context(pool, pd.DataFrame(), [], AS_OF.date()), [], estimates + [reviewed], AS_OF)
    assert result.iloc[0].projection_source_count == 3
    assert result.iloc[0].blended_fd_points == pytest.approx(baseline + .4 * (0.5 + 3 + 2) / 2.5)
    conflict = [estimates[0], dict(estimates[1], points=baseline + 10)]
    result, _ = score_slate(pool, historical_context(pool, pd.DataFrame(), [], AS_OF.date()), [], conflict, AS_OF)
    assert result.iloc[0].adjusted_fd_points == baseline
    news = dict(fanduel_id=player.fanduel_id, source='NBA', independent_group='nba',
                observed_at=(AS_OF - timedelta(minutes=15)).isoformat(), official=True,
                status='available', starter='', role='', minutes=None)
    result, _ = score_slate(pool, historical_context(pool, pd.DataFrame(), [], AS_OF.date()), [news], estimates, AS_OF)
    assert result.iloc[0].projection_source_count == 1
    assert pd.isna(result.iloc[0].blended_fd_points)


def test_owner_live_slate_archive_keeps_replay_capture_stable_on_retry():
    import json
    from io import StringIO

    import streamlit as st

    contest, daily = (frame.to_csv(index=False).encode() for frame in uploads())
    environment = {'DFS_HISTORY_OWNER_EMAIL': 'owner@example.org', 'DFS_HISTORY_INTAKE_TOKEN': 'test-only'}
    owner = {'email': environment['DFS_HISTORY_OWNER_EMAIL'], 'email_verified': True, 'is_logged_in': True}
    with (patch.dict('os.environ', environment, clear=True), patch.object(st, 'user', owner),
          patch('site_ui.public_research', return_value=([], [], [])),
          patch('site_ui.public_rotations', return_value=([], 'Unavailable')),
          patch('site_ui.public_slate_schedule', return_value=[]),
          patch('history_intake_ui.games_for_date', side_effect=OSError) as schedule,
          patch('history_intake_ui.submit_reviewed_slate', side_effect=[OSError('Retry'), None]) as archive):
        app = AppTest.from_file(str(ROOT / 'app_staging.py'), default_timeout=45).run()
        app.file_uploader(key='slate_contest').upload('contest.csv', contest, 'text/csv').run()
        app.file_uploader(key='slate_daily').upload('DAILY.csv', daily, 'text/csv').run()
        app.checkbox(key='history_intake_reviewed').check()
        app.button(key='history_intake_save').click().run()
        app.button(key='history_intake_save').click().run()
        assert not app.exception and not app.error
        assert archive.call_count == 2
        assert archive.call_args_list[0] == archive.call_args_list[1]
        schedule.assert_called_once()
        payload = json.loads(archive.call_args.args[2])
        rows = pd.read_csv(StringIO(payload['research_csv']))
        assert rows.replay_timing.eq('schedule_unverified').all()
        assert rows.replay_evidence_json.eq('[]').all()


def test_verified_fanduel_suffix_alias_keeps_team_guard_and_rejects_duplicates():
    contest, daily = uploads()
    contest.loc[0, ['Id', 'Nickname']] = ['136961-15846', 'Tim Hardaway']
    daily.loc[0, 'player'] = 'Tim Hardaway Jr.'

    def imported(contest, daily):
        return reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())[0].iloc[0]

    assert imported(contest, daily).identity_match == 'known_alias'
    other = contest.copy()
    other.loc[0, 'Id'] = '136961-998877'
    assert imported(other, daily).identity_match == 'unmatched'
    wrong_team = daily.copy()
    wrong_team.loc[0, 'team'] = 'New York Knicks'
    assert imported(contest, wrong_team).identity_match == 'unmatched'
    duplicate = pd.concat([daily, daily.iloc[[0]].assign(player='Tim Hardaway')])
    assert imported(contest, duplicate).identity_match == 'ambiguous'


def test_verified_suffix_alias_matches_public_and_historical_research():
    from datetime import timedelta

    from slate_research import match_public

    key = '136961-15846'
    pool = pd.DataFrame([dict(fanduel_id=key, fanduel_name='Tim Hardaway', team='MIA', game='OKC@MIA')])
    full = dict(player='Tim Hardaway Jr.', team='MIA', game='OKC@MIA')
    assert match_public(pool, [full])[0]['fanduel_id'] == key
    assert match_public(pool, [dict(full, team='OKC')]) == []
    assert match_public(pool.assign(fanduel_id='136961-8877'), [full]) == []
    conflict = pd.concat([pool, pool.assign(fanduel_id='136961-8877', fanduel_name='Tim Hardaway Jr.')])
    assert match_public(conflict, [full]) == []
    prior = pd.DataFrame([dict(fanduel_id='136886-15846', name='Tim Hardaway Jr.',
                               slate_date='2026-11-18', actual_minutes=24)])
    box = dict(full, game_date=AS_OF.date() - timedelta(days=1), nba_id='sample', minutes=22, started=True)
    history = historical_context(pool, prior, [box], AS_OF.date())
    assert history.iloc[0].history_games == 2
    assert history.iloc[0].recent_mpg == 23
    assert historical_context(conflict, prior, [box], AS_OF.date()).empty
