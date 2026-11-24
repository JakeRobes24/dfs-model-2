"""Read-only owner release diagnostics; never creates archive packets."""
from datetime import date
import sqlite3

import pandas as pd

from history_intake import list_slate_packets, load_slate_packet
from history_snapshot import load_latest_snapshot, load_snapshot
from nba_archive_training import prior_contests


def verify_archive_read(url, digest, token, *, latest, intake_token='', today=None):
    """Verify a fresh snapshot and one existing immutable packet; never test writes."""
    report = []
    def row(check,status,detail):
        report.append({'Check':check,'Status':status,'Detail':detail})
    if not url or not digest or not token:
        row('Remote snapshot','Not configured','Remote URL, digest and read credential are required.')
        return pd.DataFrame(report)
    try:
        frame, status = (load_latest_snapshot(url,digest,token) if latest
                         else load_snapshot(url,digest,token))
        if frame.empty or not status.startswith('History loaded (read-only).'):
            raise ValueError('No verified historical rows.')
        row('Remote snapshot','Verified',f'{len(frame)} research rows; fresh checksum and SQLite integrity check.')
    except (ValueError,OSError,sqlite3.Error,TypeError,KeyError,AttributeError):
        row('Remote snapshot','Not verified','Fresh snapshot could not be loaded or verified.')
        return pd.DataFrame(report)
    # A repository-readable token does not prove write permission.
    row('Archive write credential','Configured' if intake_token else 'Not configured',
        'Write access and backup publication require a real reviewed save; no test write was attempted.')
    choices = prior_contests(frame,today or date.today(),limit=3)
    matched = False
    for day,contest in choices:
        try:
            commit,folder,versions = list_slate_packets(token,day,contest)
            if not versions:
                continue
            pool,_ = load_slate_packet(token,commit,folder,versions[0])
            row('Existing archive packet','Verified',f'{day} · contest {contest} · {len(pool)} players; immutable packet checksum verified.')
            matched = True
            break
        except (ValueError,OSError,TypeError,KeyError,AttributeError):
            continue
    if not matched:
        row('Existing archive packet','Not verified','No readable packet found among up to three recent historical dates.')
    return pd.DataFrame(report)
