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
