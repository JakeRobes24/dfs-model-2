from datetime import date
from unittest.mock import patch
import pandas as pd

from release_archive_diagnostics import verify_archive_read


def test_fresh_archive_diagnostic_checks_existing_packet_without_writing():
    history=pd.DataFrame({'slate_date':['2026-11-18'],'fanduel_id':['123-1']})
    with patch('release_archive_diagnostics.load_latest_snapshot',return_value=(history,'History loaded (read-only). Published backup abcdef0.')) as snapshot, patch(
            'release_archive_diagnostics.list_slate_packets',return_value=('commit','folder',['version'])) as listing, patch(
            'release_archive_diagnostics.load_slate_packet',return_value=(history,None)) as packet:
        report=verify_archive_read('url','digest','read',latest=True,intake_token='write',today=date(2026,11,24))
        assert report.Status.tolist()==['Verified','Configured','Verified']
        snapshot.assert_called_once_with('url','digest','read')
        listing.assert_called_once_with('read',date(2026,11,18),'123')
        packet.assert_called_once_with('read','commit','folder','version')
        assert 'Write access' in report.Detail.iloc[1]
    with patch('release_archive_diagnostics.load_latest_snapshot',side_effect=ValueError('private detail')) as snapshot, patch(
            'release_archive_diagnostics.list_slate_packets') as listing:
        report=verify_archive_read('url','digest','read',latest=True)
        assert report.Status.tolist()==['Not verified']
        assert 'private detail' not in report.to_string()
        listing.assert_not_called()
    assert verify_archive_read('url','digest','',latest=True).Status.tolist()==['Not configured']
