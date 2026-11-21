"""Optional Streamlit history panel; add to app.py only after staging review."""
import os
import streamlit as st
from history_readonly import load_history

def render_history_panel():
    with st.expander('Historical player results (read-only)', expanded=False):
        path = os.environ.get('DFS_HISTORY_DB', '')
        if not path:
            st.info('No persistent history database configured. Existing CSV workflow remains available.')
            return
        frame, status = load_history(path)
        st.caption(status)
        if not frame.empty:
            st.metric('Historical research rows', len(frame))
            st.metric('Rows with verified actual FD points', int(frame.actual_fd_points.notna().sum()))
            st.dataframe(frame, hide_index=True, use_container_width=True)
