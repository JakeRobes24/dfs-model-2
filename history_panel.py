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


def render_history_panel():
    with st.expander('Historical player results (read-only)', expanded=False):
        path = os.environ.get('DFS_HISTORY_DB')
        snapshot_url = os.environ.get('DFS_HISTORY_SNAPSHOT_URL')
        if path:
            frame, status = load_history(path)
        elif snapshot_url:
            owner_email = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
            if not owner_email:
                st.info('Remote history is disabled until owner sign-in is configured.')
                return
            if not owner_can_view_history(owner_email, st.user):
                st.info('Sign in with the authorized account to view historical results.')
                if st.user.get('is_logged_in'):
                    if st.button('Sign out', key='dfs_history_logout'):
                        st.logout()
                elif st.button('Sign in', key='dfs_history_login'):
                    st.login()
                return
            if st.button('Sign out', key='dfs_history_logout'):
                st.logout()
            try:
                configured = (snapshot_url, os.environ.get('DFS_HISTORY_SNAPSHOT_SHA256', ''))
                frame, status = load_configured_snapshot(
                    *configured, os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN', ''),
                )
            except (OSError, ValueError, sqlite3.Error):
                st.warning('History snapshot could not be loaded or verified. Use the verified CSV fallback.')
                return
        else:
            st.info('No persistent history database configured. Existing CSV workflow remains available.')
            return

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
