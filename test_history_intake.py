import json
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd
import pytest

from history_intake import make_submission, submit_reviewed_slate
from model import consensus

ROOT = Path(__file__).resolve().parent
SLATE = date(2026, 11, 20)


def reviewed_pool():
    return consensus(pd.read_csv(ROOT / 'nov20_reconciled_example.csv', dtype={'fanduel_id': str}))


def test_submission_keeps_contest_versions_and_refuses_bad_actuals():
    pool = reviewed_pool()
    pid = pool.fanduel_id.iloc[0]
    actual = f'fanduel_id,actual_minutes,actual_fd_points,actuals_source\n{pid},12,20,NBA\n'
    path, blob = make_submission(pool, SLATE, actuals=actual)
    data = json.loads(blob)
    assert data['actuals_csv'] == actual
    assert path.startswith(f'incoming-app/{SLATE}/{pid.split("-")[0]}/')
    assert make_submission(pool, SLATE, actuals=actual) == (path, blob)
    assert make_submission(pool, SLATE)[0] != path
    with pytest.raises(ValueError, match='numeric'):
        make_submission(pool, SLATE, actuals=actual.replace(',20,', ',bad,'))
    with pytest.raises(ValueError, match='source'):
        make_submission(pool, SLATE, actuals=actual.replace('NBA', ''))
    pool.loc[pool.index[-1], 'fanduel_id'] = '999999-987654'
    with pytest.raises(ValueError, match='one contest'):
        make_submission(pool, SLATE)


def test_retry_confirms_identical_packet_without_overwriting():
    path, raw = make_submission(reviewed_pool(), SLATE)
    with patch('history_intake.build_opener') as opener:
        call = opener.return_value.open
        call.side_effect = [HTTPError('https://example.org', 422, 'already exists', {}, None), BytesIO(raw)]
        assert submit_reviewed_slate('test-only', path, raw) is None
        put = call.call_args_list[0].args[0]
        get = call.call_args_list[1].args[0]
        assert put.full_url.startswith('https://api.github.com/repos/JakeRobes24/dfs-model-2-history/contents/incoming-app/')
        assert put.get_method() == 'PUT' and get.get_method() == 'GET'
        assert 'sha' not in json.loads(put.data)
        with pytest.raises(ValueError):
            submit_reviewed_slate('test-only', '.github/workflows/override.yml', raw)


def test_only_verified_owner_can_submit_the_current_pool():
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    csv = (ROOT / 'nov20_reconciled_example.csv').read_bytes()
    environment = {'DFS_HISTORY_OWNER_EMAIL': 'owner@example.org', 'DFS_HISTORY_INTAKE_TOKEN': 'test-only'}
    owner = {'email': environment['DFS_HISTORY_OWNER_EMAIL'], 'email_verified': True, 'is_logged_in': True}
    with patch.dict('os.environ', environment, clear=True), patch('history_intake_ui.submit_reviewed_slate') as send:
        with patch.object(st, 'user', dict(owner, email_verified=False)):
            app = AppTest.from_file(str(ROOT / 'app_staging.py')).run()
            app.radio(key='site_view').set_value('History and advanced').run()
            app.file_uploader(key='base').upload('pool.csv', csv, 'text/csv').run()
            assert all(button.label != 'Save slate and start backup' for button in app.button)
            send.assert_not_called()
        with patch.object(st, 'user', owner):
            app = AppTest.from_file(str(ROOT / 'app_staging.py')).run()
            app.radio(key='site_view').set_value('History and advanced').run()
            app.file_uploader(key='base').upload('pool.csv', csv, 'text/csv').run()
            send.return_value = 'abcdef0'
            app.button(key='history_intake_save').click().run()
            send.assert_not_called()
            app.checkbox(key='history_intake_reviewed').check()
            app.button(key='history_intake_save').click().run()
            assert not app.exception and not app.error
            send.assert_called_once()
            _, path, raw = send.call_args.args
            packet = json.loads(raw)
            assert packet['contest_id'] in path and 'adjusted_fd_points' in packet['research_csv']


def test_existing_key_is_reused_only_for_main_site_configuration():
    from history_intake_ui import PRODUCTION_CALLBACK, _intake_token
    from history_panel import NOV20_BACKFILL

    settings = {
        'DFS_HISTORY_SNAPSHOT_TOKEN': 'existing-test-key',
        'DFS_HISTORY_SNAPSHOT_URL': NOV20_BACKFILL[0],
        'DFS_HISTORY_SNAPSHOT_SHA256': NOV20_BACKFILL[1],
    }
    with patch.dict('os.environ', settings, clear=True):
        with patch('history_intake_ui.st.secrets', {'auth': {'redirect_uri': PRODUCTION_CALLBACK}}):
            assert _intake_token() == 'existing-test-key'
            with patch.dict('os.environ', {'DFS_HISTORY_SNAPSHOT_URL': 'https://other.example.org/history.sqlite'}):
                assert _intake_token() == ''
        with patch('history_intake_ui.st.secrets', {'auth': {'redirect_uri': 'https://preview.example.org/oauth2callback'}}):
            assert _intake_token() == ''


def test_read_only_recovery_receipt_checks_exact_bytes_at_pinned_commit():
    from history_intake import recovery_packet_path,check_recovery_receipt
    path,raw=make_submission(reviewed_pool(),SLATE)
    assert recovery_packet_path(raw)==path
    with patch('history_snapshot.history_head',return_value='a'*40), patch(
            'history_snapshot._request',return_value=BytesIO(raw)) as read:
        result=check_recovery_receipt('fixture',raw)
        assert result==dict(path=path,commit='a'*40,status='verified')
        assert read.call_args.args[0].endswith(path+'?ref='+'a'*40)
        assert read.call_args.kwargs==dict(raw=True)
    with patch('history_snapshot.history_head',return_value='a'*40), patch(
            'history_snapshot._request',side_effect=HTTPError('https://example.org',404,'missing',{},None)):
        assert check_recovery_receipt('fixture',raw)['status']=='not_found'
    with patch('history_snapshot.history_head',return_value='a'*40), patch(
            'history_snapshot._request',return_value=BytesIO(raw+b' ')):
        with pytest.raises(ValueError,match='bytes'):
            check_recovery_receipt('fixture',raw)
    for bad in (b'',b'[]',b'{"version":1,"slate_date":"../x"}'):
        with pytest.raises(ValueError):
            recovery_packet_path(bad)


def test_prepare_packet_does_not_submit_and_save_reuses_exact_bytes():
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    environment={'DFS_HISTORY_OWNER_EMAIL':'owner@example.org','DFS_HISTORY_INTAKE_TOKEN':'test-only'}
    owner={'email':'owner@example.org','email_verified':True,'is_logged_in':True}
    csv=(ROOT/'nov20_reconciled_example.csv').read_bytes()
    with patch.dict('os.environ',environment,clear=True),patch.object(st,'user',owner),patch(
            'history_intake_ui.submit_reviewed_slate',return_value='abcdef0') as send:
        app=AppTest.from_file(str(ROOT/'app_staging.py')).run()
        app.radio(key='site_view').set_value('History and advanced').run()
        app.file_uploader(key='base').upload('pool.csv',csv,'text/csv').run()
        app.checkbox(key='history_intake_reviewed').check()
        app.button(key='history_intake_prepare').click().run()
        assert not app.exception
        send.assert_not_called()
        path,raw=app.session_state['history_prepared_packet']
        assert path.endswith('.json')
        app.button(key='history_intake_save').click().run()
        assert not app.exception
        send.assert_called_once_with('test-only',path,raw)
