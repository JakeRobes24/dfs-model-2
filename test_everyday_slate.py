"""Exercise the default two-file workflow with controlled sources."""
from collections import Counter
from datetime import date, datetime, timedelta
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
    # Synthetic teams and two matchups; test standard classic team limits.
    teams = [['BOS','NYK','CHI','TOR'][i%4] for i in range(len(base))]
    games = ['BOS@NYK' if t in ('BOS','NYK') else 'CHI@TOR' for t in teams]
    contest = base.assign(game=games, team=teams).rename(columns={
        'fanduel_id': 'Id', 'fanduel_name': 'Nickname', 'salary': 'Salary', 'team': 'Team',
        'game': 'Game', 'position': 'Position', 'roster_eligibility': 'Roster Position',
        'injury_flag': 'Injury Indicator',
    })
    daily = base.assign(team=teams, gameInfo=games).rename(columns={
        'fanduel_name': 'player', 'projected_minutes': 'minutes', 'projected_fd_points': 'fantasy',
    })
    return contest, daily


def test_contest_authority_and_ambiguous_projection_matches():
    contest, daily = uploads()
    daily = daily.assign(points=20, rebounds=0, assists=-1)
    daily = pd.concat([daily, daily.iloc[:1]], ignore_index=True)
    daily.loc[2, 'team'] = 'BOS'
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
          patch('slate_research.get_reference_research', return_value=({}, {})),
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
        _, (lineups, comparison, alternative), _ = app.session_state['slate_results']
        assert len(comparison) == 4 and len(alternative) == 9
        for _, lineup in lineups.groupby('lineup'):
            assert Counter(lineup.slot) == Counter(SLOTS)
            assert lineup.fanduel_id.nunique() == 9 and lineup.salary.sum() <= 60000
            for row in lineup.itertuples():
                eligibility = contest.loc[contest.Id.eq(row.fanduel_id), 'Roster Position'].iat[0]
                assert row.slot in allowed_slots(eligibility)
        assert set(alternative.fanduel_id) != set(lineups[lineups.lineup.eq(1)].fanduel_id)
        schedule.return_value = [dict(awayTeam={'teamTricode': 'BOS'}, homeTeam={'teamTricode': 'NYK'},
                                      gameTimeUtc=datetime.now(ET).isoformat(), gameStatus=2),
                                 dict(awayTeam={'teamTricode':'CHI'}, homeTeam={'teamTricode':'TOR'},
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
        'team': ['BOS','NYK','CHI']*3+['NYK','CHI'],
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
    # The first matchup locks; all remaining players remain open.
    with (patch('site_ui.public_research', return_value=([], [], [])),
          patch('site_ui.public_rotations', return_value=([], 'Unavailable')),
          patch('site_ui.public_slate_schedule', return_value=[
              dict(awayTeam={'teamTricode': away}, homeTeam={'teamTricode': home},
                   gameTimeUtc=(datetime.now(ET) + timedelta(minutes=45)).isoformat(), gameStatus=1)
              for away,home in [('BOS','NYK'),('CHI','TOR')]
          ]),
          patch('site_ui.started_contest_games', return_value=(set(), True)) as game_state):
        app = AppTest.from_file(str(ROOT / 'app_staging.py'), default_timeout=45).run()
        app.file_uploader(key='slate_contest').upload('contest.csv', contest.to_csv(index=False).encode(), 'text/csv')
        app.file_uploader(key='slate_daily').upload('DAILY.csv', daily.to_csv(index=False).encode(), 'text/csv').run()
        app.button(key='slate_optimize').click().run()
        lineups = app.session_state['slate_results'][1][0]
        entered = lineups.loc[lineups.lineup.eq(1), ['slot', 'fanduel_id']]
        game_state.return_value = ({'BOS/NYK'}, True)
        app.run()
        assert app.radio(key='slate_swap_entry_method').value == 'Select players'
        assert not any(button.key == 'slate_late_swap_run' for button in app.button)
        ordered = entered.sort_values('slot', key=lambda slots: slots.map(SLOTS.index), kind='stable')
        for picker, player in zip((item for item in app.selectbox if (item.key or '').startswith('slate_swap_')),
                                  ordered.fanduel_id, strict=True):
            picker.select(player)
        app.run()
        app.button(key='slate_late_swap_run').click().run()
        assert not app.exception and not app.error
        manual_swap = app.session_state['late_swap_result'][1]
        assert manual_swap.entered_fanduel_id.tolist() == ordered.fanduel_id.tolist()
        app.radio(key='slate_swap_entry_method').set_value('Upload CSV').run()
        app.file_uploader(key='slate_late_swap').upload('entered.csv', entered.to_csv(index=False).encode(),
                                                      'text/csv').run()
        app.button(key='slate_late_swap_run').click().run()
        assert not app.exception and not app.error
        assert app.button(key='slate_optimize').disabled
        swap = app.session_state['late_swap_result'][1]
        locked = set(entered.fanduel_id) & set(contest.loc[contest.Game.eq('BOS@NYK'), 'Id'])
        assert locked and set(swap.loc[swap.locked, 'fanduel_id']) == locked
        assert swap.loc[swap.locked, 'changed'].eq(False).all()
        assert any('Projected points change' in caption.value for caption in app.caption)
        assert any('UTIL 2' in frame.value.get('slot', []).tolist() for frame in app.dataframe if 'slot' in frame.value)

        # A game starting during a solve invalidates the old and new swap
        # results, even when the returned roster was legal at solve start.
        def crossing_lock(*args, **kwargs):
            assert 0 < kwargs['time_budget_seconds'] <= 35
            game_state.return_value = ({'BOS/NYK','CHI/TOR'}, True)
            return swap
        with patch('site_ui.optimize_late_swap', side_effect=crossing_lock):
            app.button(key='slate_late_swap_run').click().run()
        assert not app.exception
        assert any('Game locks changed during optimization' in e.value for e in app.error)
        assert 'late_swap_result' not in app.session_state
        app.run()
        assert not app.exception
        assert not any(b.key=='slate_late_swap_run' for b in app.button)



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
    import json
    inputs = json.loads(result.iloc[0].projection_sources_json)
    assert len(inputs) == 3
    assert {row['source'] for row in inputs} == {DFF, PROPSIMS, LINEUPEXPERTS_TODAY}
    assert sum(row['points'] * row['weight'] for row in inputs) / sum(
        row['weight'] for row in inputs) == pytest.approx(result.iloc[0].independent_fd_points)
    assert all(pd.Timestamp(row['observed_at']) <= AS_OF for row in inputs)
    later, _ = score_slate(pool, historical_context(pool, pd.DataFrame(), [], AS_OF.date()),
                           [], estimates + [reviewed], AS_OF + timedelta(minutes=1))
    assert later.iloc[0].projection_sources_json == result.iloc[0].projection_sources_json
    assert later.iloc[0].adjusted_fd_points == result.iloc[0].adjusted_fd_points
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


def test_prepared_contingency_runtime_survives_news_refresh():
    """Controlled Streamlit runtime test; no real network or entry submission."""
    contest, daily = uploads()
    contest['Injury Indicator'] = ''
    scratch = contest.loc[0, 'Id']
    contest.loc[0, ['Injury Indicator', 'Salary']] = ['Q', 3500]
    daily.loc[0, ['fantasy', 'minutes']] = [85., 40.]
    schedule = [dict(awayTeam={'teamTricode':away}, homeTeam={'teamTricode':home},
                     gameTimeUtc=(datetime.now(ET)+timedelta(minutes=45)).isoformat(), gameStatus=1)
                for away,home in [('BOS','NYK'),('CHI','TOR')]]
    with (patch('site_ui.public_research', return_value=([], [], [])) as news,
          patch('site_ui.public_rotations', return_value=([], 'Unavailable')),
          patch('site_ui.public_slate_schedule', return_value=schedule) as clock):
        app = AppTest.from_file(str(ROOT/'app_staging.py'),default_timeout=60).run()
        app.file_uploader(key='slate_contest').upload('contest.csv',contest.to_csv(index=False).encode(),'text/csv')
        app.file_uploader(key='slate_daily').upload('DAILY.csv',daily.to_csv(index=False).encode(),'text/csv').run()
        app.button(key='slate_optimize').click().run()
        assert not app.exception and not app.error
        lineups=app.session_state['slate_results'][1][0]
        entered=lineups.loc[lineups.lineup.eq(1),['slot','fanduel_id']]
        assert scratch in entered.fanduel_id.tolist()
        app.button(key='slate_contingencies_run').click().run()
        assert not app.exception and not app.error
        saved=app.session_state['prepared_contingency_archive']
        assert saved[1]['completed_scenarios']==1
        app.file_uploader(key='prepared_entered_roster').upload('entry.csv',entered.to_csv(index=False).encode(),'text/csv').run()
        app.checkbox(key='prepared_activate').check()
        app.button(key='prepared_validate').click().run()
        assert any('not confirmed' in w.value for w in app.warning)
        assert not any('validated_at_snapshot' in c.value for c in app.caption)
        app.checkbox(key='prepared_activate').uncheck()
        app.button(key='prepared_validate').click().run()
        assert any('hypothetical_preview' in c.value for c in app.caption)
        note=dict(player=contest.loc[0,'Nickname'],team='BOS',game='BOS@NYK',
                  fanduel_id=scratch,source='NBA',independent_group='nba',official=True,
                  status='out',starter='',role='',minutes=None,
                  observed_at=(datetime.now(ET)-timedelta(minutes=1)).isoformat())
        news.return_value=([note],[],[])
        app.run()
        assert not app.exception
        assert app.session_state['prepared_contingency_archive'][0]==saved[0]
        old = app.session_state['last_complete_portfolio'][2]
        pd.testing.assert_frame_equal(old,lineups)
        assert any('Earlier candidate snapshot' in w.value for w in app.warning)
        assert any('current_eligible' in d.value.columns for d in app.dataframe)
        # A failed new solve cannot remove or certify the old four entries.
        with patch('site_ui.generate_and_challenge', return_value=(pd.DataFrame(),pd.DataFrame(),pd.DataFrame())):
            app.button(key='slate_optimize').click().run()
            assert not app.exception
            pd.testing.assert_frame_equal(app.session_state['last_complete_portfolio'][2],lineups)
            assert any('Earlier candidate snapshot' in w.value for w in app.warning)
        # A partial current result does not replace the last complete snapshot.
        partial_rows=lineups.loc[lineups.lineup.eq(2)].copy()
        partial_rows=partial_rows.assign(lineup=1)
        with patch('site_ui.generate_and_challenge', return_value=(partial_rows,pd.DataFrame(),pd.DataFrame())):
            app.button(key='slate_optimize').click().run()
            assert not app.exception
            pd.testing.assert_frame_equal(app.session_state['last_complete_portfolio'][2],lineups)
            assert any('Earlier candidate snapshot' in w.value for w in app.warning)

        app.checkbox(key='prepared_activate').check()
        app.button(key='prepared_validate').click().run()
        assert not app.exception and not app.error
        assert any('validated_at_snapshot' in c.value for c in app.caption)
        clock.return_value=[dict(schedule[0],gameStatus=2),schedule[1]]
        app.run()
        app.button(key='prepared_validate').click().run()
        assert not app.exception
        assert not any('validated_at_snapshot' in c.value for c in app.caption)



@pytest.mark.parametrize('change', [
    {'observed_at': (AS_OF-timedelta(hours=7)).isoformat()},
    {'observed_at': (AS_OF+timedelta(minutes=1)).isoformat()},
    {'observed_at': AS_OF.replace(tzinfo=None).isoformat()},
    {'minutes': 'not numeric'},
    {'minutes': 49},
    {'independent_group': ''},
])
def test_unusable_minutes_cannot_adjust_provisional_projection(change):
    contest, daily = uploads()
    pool, _, _ = reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())
    player = pool.iloc[0]
    history = pd.DataFrame([dict(player=player.fanduel_name, recent_mpg=player.projected_minutes + 3,
                                 history_games=3)])
    estimate = dict(fanduel_id=player.fanduel_id, source=RW_MINUTES, independent_group='rotowire',
                    observed_at=AS_OF.isoformat(), official=False, status='', starter='', role='',
                    minutes=player.projected_minutes+3)
    baseline, _ = score_slate(pool, history, [], [], AS_OF)
    scored, _ = score_slate(pool, history, [dict(estimate, **change)], [], AS_OF)
    assert scored.iloc[0].adjusted_fd_points == pytest.approx(baseline.iloc[0].adjusted_fd_points)
    assert pd.isna(scored.iloc[0].independent_minutes)


def test_superseded_and_conflicting_minutes_do_not_corroborate():
    from slate_research import PROPSIMS
    contest, daily = uploads()
    pool, _, _ = reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())
    player = pool.iloc[0]
    history = pd.DataFrame([dict(player=player.fanduel_name, recent_mpg=player.projected_minutes + 3,
                                 history_games=3)])
    estimate = dict(fanduel_id=player.fanduel_id, source=RW_MINUTES, independent_group='rotowire',
                    observed_at=(AS_OF-timedelta(minutes=30)).isoformat(), official=False, status='',
                    starter='', role='', minutes=player.projected_minutes+3)
    second = dict(estimate, source=PROPSIMS, independent_group='propsims')
    official = dict(estimate, source='NBA', independent_group='nba', official=True, status='available',
                    minutes=None, observed_at=AS_OF.isoformat())
    baseline, _ = score_slate(pool, history, [], [], AS_OF)
    for notes in ([estimate, second, official],
                  [estimate, second, dict(estimate, minutes=player.projected_minutes+5)]):
        scored, _ = score_slate(pool, history, notes, [], AS_OF)
        assert scored.iloc[0].adjusted_fd_points == pytest.approx(baseline.iloc[0].adjusted_fd_points)
    updated = dict(estimate, observed_at=AS_OF.isoformat())
    stale_out = dict(official, status='out', observed_at=(AS_OF-timedelta(hours=1)).isoformat())
    scored, _ = score_slate(pool, history, [stale_out, official, updated], [], AS_OF)
    assert scored.iloc[0].adjusted_minutes == pytest.approx(player.projected_minutes+1)
    assert scored.iloc[0].eligible


def test_naive_point_timestamp_cannot_supply_independent_projection():
    from slate_research import DFF
    contest, daily = uploads()
    pool, _, _ = reconcile_exports(contest.to_csv(index=False).encode(), daily.to_csv(index=False).encode())
    player = pool.iloc[0]
    history = pd.DataFrame([dict(player=player.fanduel_name, recent_mpg=player.projected_minutes + 3,
                                 history_games=3)])
    projection = dict(fanduel_id=player.fanduel_id, source=DFF,
                      observed_at=AS_OF.astimezone(__import__('datetime').timezone.utc).replace(tzinfo=None).isoformat(),
                      points=player.projected_fd_points+3)
    scored, _ = score_slate(pool, history, [], [projection], AS_OF)
    assert scored.iloc[0].projection_source_count == 0


def test_nov25_verified_short_names_keep_contest_identity_and_team_guards():
    # Real identity mappings, synthetic projection values; no private CSV included.
    cases = [
        ('84682','Michael Porter','Michael Porter Jr.'),
        ('188422','Jaime Jaquez','Jaime Jaquez Jr.'),
        ('203719','Terrence Shannon','Terrence Shannon Jr.'),
        ('66968','Derrick Jones','Derrick Jones Jr.'),
        ('248950','Christian Anderson','Christian Anderson Jr.'),
        ('157834','Bones Hyland',"Nah'Shon Hyland"),
        ('189467','Craig Porter','Craig Porter Jr.'),
        ('84695','Gary Trent','Gary Trent Jr.'),
        ('171661','Scotty Pippen','Scotty Pippen Jr.'),
        ('188444','GG Jackson','Gregory Jackson'),
    ]
    for suffix, short, full in cases:
        from test_nba_csv_pipeline_integration import synthetic_exports
        from io import BytesIO
        c, d = synthetic_exports()
        contest, daily = pd.read_csv(BytesIO(c)), pd.read_csv(BytesIO(d))
        contest.loc[0, ['Id','Nickname']] = ['99999-'+suffix,short]
        daily.loc[0,'player'] = full
        def imported(c,d):
            return reconcile_exports(c.to_csv(index=False).encode(),d.to_csv(index=False).encode())[0].iloc[0]
        assert imported(contest,daily).identity_match == 'known_alias'
        wrong_id = contest.copy()
        wrong_id.loc[0,'Id'] = '99999-998877'
        assert imported(wrong_id,daily).identity_match == 'unmatched'
        wrong_team = daily.copy()
        wrong_team.loc[0,'team'] = 'Washington Wizards'
        assert imported(contest,wrong_team).identity_match == 'unmatched'
        duplicate = pd.concat([daily,daily.iloc[[0]].assign(player=short)])
        assert imported(contest,duplicate).identity_match == 'ambiguous'
