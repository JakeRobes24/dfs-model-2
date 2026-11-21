from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pytest

from history_backup import sha256
from history_snapshot import load_snapshot

BACKUP = Path(__file__).resolve().parent.parent / 'nov20_player_history_verified_backup.sqlite'
URL = 'https://history.example.org/snapshots/nov20.sqlite'


def test_reopens_verified_snapshot_after_fresh_fetches():
    with patch('history_snapshot.build_opener') as opener:
        opener.return_value.open.side_effect = [
            BytesIO(BACKUP.read_bytes()),
            BytesIO(BACKUP.read_bytes()),
        ]
        for _ in range(2):
            rows, status = load_snapshot(URL, sha256(BACKUP), 'test-token')
            assert len(rows) == 247
            assert rows.actual_fd_points.notna().sum() == 17
            assert status == 'History loaded (read-only).'
        request = opener.return_value.open.call_args.args[0]
        assert request.get_header('Authorization') == 'Bearer test-token'


def test_rejects_wrong_checksum():
    with patch('history_snapshot.build_opener') as opener:
        opener.return_value.open.return_value = BytesIO(b'wrong version')
        with pytest.raises(ValueError, match='checksum mismatch'):
            load_snapshot(URL, '0' * 64)


def test_reports_failed_retrieval():
    with patch('history_snapshot.build_opener') as opener:
        opener.return_value.open.side_effect = URLError('object unavailable')
        with pytest.raises(URLError):
            load_snapshot(URL, '0' * 64)


def test_github_requests_snapshot_bytes_at_the_pinned_ref():
    url = 'https://api.github.com/repos/owner/private/contents/history.sqlite?ref=immutable'
    with patch('history_snapshot.build_opener') as opener:
        opener.return_value.open.return_value = BytesIO(BACKUP.read_bytes())
        load_snapshot(url, sha256(BACKUP), 'test-token')
        request = opener.return_value.open.call_args.args[0]
        assert request.full_url == url
        assert request.get_header('Accept') == 'application/vnd.github.raw+json'


def test_history_only_loads_for_verified_owner():
    from history_panel import render_history_panel

    owner = 'owner@example.org'
    settings = {'DFS_HISTORY_OWNER_EMAIL': owner, 'DFS_HISTORY_SNAPSHOT_URL': URL}
    cases = [
        ({}, False),
        ({'is_logged_in': True, 'email_verified': False, 'email': owner}, False),
        ({'is_logged_in': True, 'email_verified': True, 'email': 'other@example.org'}, False),
        ({'is_logged_in': True, 'email_verified': True, 'email': owner}, True),
    ]
    for identity, permitted in cases:
        with patch.dict('os.environ', settings, clear=True), patch('history_panel.st') as st, patch(
            'history_panel.load_configured_snapshot'
        ) as load:
            st.user = identity
            st.button.return_value = False
            load.return_value = (type('Result', (), {'empty': True})(), 'Loaded')
            render_history_panel()
            assert load.called is permitted
