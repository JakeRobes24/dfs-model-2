"""Optional read-only history panel for staging."""
import os
import sqlite3

import streamlit as st

from history_readonly import load_history
from history_snapshot import load_latest_snapshot, load_snapshot


# Upgrade the exact Nov. 20 preview pin while preserving custom snapshot settings.
_HISTORY_API = 'https://api.github.com/repos/JakeRobes24/dfs-model-2-history/contents/'
NOV20_ORIGINAL = (
    _HISTORY_API + 'nov20_player_history_verified_backup.sqlite?ref=ead20573bc00cfd07750a1ce24587ef4a6a5405f',
    '419410468b23f912e64fcd03a5516a96578484c3d39f89f5682a35808b2c3cad',
)
NOV20_BACKFILL = (
    _HISTORY_API + 'nov20_player_history_backfill_v2.sqlite?ref=337b35763b9526049837051955df3e1812897c0f',
    '4485bb7fc97e4417f85082ffc30115ef220f7e3054076d1e3ed18db1e7b6a81d',
)


@st.cache_data(ttl=300, max_entries=2, show_spinner=False)
def load_configured_snapshot(url, digest, token):
    if (url, digest) in (NOV20_ORIGINAL, NOV20_BACKFILL):
        return load_latest_snapshot(*NOV20_BACKFILL, token)
    return load_snapshot(url, digest, token)


def owner_can_view_history(owner_email, identity):
    return bool(
        identity.get('is_logged_in')
        and identity.get('email_verified') is True
        and (identity.get('email') or '').strip().casefold() == owner_email.strip().casefold()
    )


def configured_history():
    path = os.environ.get('DFS_HISTORY_DB')
    if path:
        return load_history(path)
    url = os.environ.get('DFS_HISTORY_SNAPSHOT_URL')
    if not url:
        return None, 'No persistent history database configured. Existing CSV workflow remains available.'
    owner = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
    if not owner:
        return None, 'Remote history is disabled until owner sign-in is configured.'
    if not owner_can_view_history(owner, st.user):
        return None, 'Sign in with the authorized account to view historical results.'
    try:
        return load_configured_snapshot(
            url, os.environ.get('DFS_HISTORY_SNAPSHOT_SHA256', ''),
            os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN', ''),
        )
    except (OSError, ValueError, sqlite3.Error):
        return None, 'History snapshot could not be loaded or verified. Use the verified CSV fallback.'


def render_history_panel():
    frame, status = configured_history()
    with st.expander('Historical player results (read-only)', expanded=False):
        if os.environ.get('DFS_HISTORY_SNAPSHOT_URL') and os.environ.get('DFS_HISTORY_OWNER_EMAIL'):
            if st.user.get('is_logged_in'):
                if st.button('Sign out', key='dfs_history_logout'):
                    st.logout()
            elif st.button('Sign in', key='dfs_history_login'):
                st.login()
        owner = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
        url = os.environ.get('DFS_HISTORY_SNAPSHOT_URL', '')
        if owner and url and owner_can_view_history(owner, st.user):
            if st.button('Verify live archive connection (read-only)', key='history_release_verify'):
                from history_intake_ui import _intake_token
                from release_archive_diagnostics import verify_archive_read
                from datetime import datetime
                from zoneinfo import ZoneInfo
                digest = os.environ.get('DFS_HISTORY_SNAPSHOT_SHA256', '')
                token = os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN', '')
                use_latest = (url, digest) in (NOV20_ORIGINAL, NOV20_BACKFILL)
                if use_latest:
                    url, digest = NOV20_BACKFILL
                with st.spinner('Verifying fresh backup and existing archive packet…'):
                    report = verify_archive_read(url, digest, token, latest=use_latest,
                        intake_token=_intake_token(), today=datetime.now(ZoneInfo('America/New_York')).date())
                st.dataframe(report, hide_index=True)
                st.caption('Read-only checks do not certify write permissions or backup publication. No archive records were changed.')
        if frame is None:
            st.info(status)
            return None

        st.caption(status)
        if not frame.empty:
            st.metric('Historical research rows', len(frame))
            score_label = 'Rows with recorded actual FD points' if 'outcome' in frame else 'Rows with verified actual FD points'
            st.metric(score_label, int(frame.actual_fd_points.notna().sum()))
            if 'outcome' in frame:
                st.metric('Did not play', int(frame.outcome.eq('did_not_play').sum()))
                disagreements = int(frame.prior_comparison.eq('conflict').sum())
                if disagreements:
                    st.caption(f'{disagreements} prior results differ from the official box score. Both values are shown.')
            st.dataframe(frame, hide_index=True, use_container_width=True)
    return frame
