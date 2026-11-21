"""Optional read-only history panel for staging."""
import os
import sqlite3

import streamlit as st

from history_readonly import load_history
from history_snapshot import load_snapshot


@st.cache_data(ttl=300, max_entries=2, show_spinner=False)
def load_configured_snapshot(url, digest, token):
    return load_snapshot(url, digest, token)


def render_history_panel():
    with st.expander('Historical player results (read-only)', expanded=False):
        path = os.environ.get('DFS_HISTORY_DB')
        snapshot_url = os.environ.get('DFS_HISTORY_SNAPSHOT_URL')
        if path:
            frame, status = load_history(path)
        elif snapshot_url:
            try:
                frame, status = load_configured_snapshot(
                    snapshot_url,
                    os.environ.get('DFS_HISTORY_SNAPSHOT_SHA256', ''),
                    os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN', ''),
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
            st.metric('Rows with verified actual FD points', int(frame.actual_fd_points.notna().sum()))
            st.dataframe(frame, hide_index=True, use_container_width=True)
