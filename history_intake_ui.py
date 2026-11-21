"""Owner-only slate archive controls."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from history_intake import MAX_PACKET, make_submission, submit_reviewed_slate
from history_panel import owner_can_view_history


def render_slate_archive(pool):
    token = os.environ.get('DFS_HISTORY_INTAKE_TOKEN', '').strip()
    owner = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
    if not token or not owner or not owner_can_view_history(owner, st.user):
        return

    with st.expander('Save reviewed slate to private history'):
        st.caption('Saves the current full pool and projections. Include verified actuals or a final lineup CSV when available.')
        with st.form('history_intake'):
            slate = st.date_input('Slate date (ET)', datetime.now(ZoneInfo('America/New_York')).date())
            actual = st.file_uploader('Verified actuals CSV (optional)', type='csv')
            lineups = st.file_uploader('Final lineups CSV (optional)', type='csv')
            confirmed = st.checkbox('I reviewed these inputs for this contest.', key='history_intake_reviewed')
            save = st.form_submit_button('Save slate and start backup', key='history_intake_save')
        if save:
            if not confirmed:
                st.warning('Confirm the slate inputs before saving.')
                return
            try:
                optional = {}
                for key, file in (('actuals', actual), ('lineups', lineups)):
                    if file is not None:
                        if file.size > MAX_PACKET:
                            raise ValueError('Each upload must be smaller than 8 MiB.')
                        optional[key] = file.getvalue().decode('utf-8-sig')
                path, raw = make_submission(pool, slate, **optional)
                commit = submit_reviewed_slate(token, path, raw)
            except (ValueError, OSError) as error:
                st.error(str(error))
            else:
                if commit:
                    st.success(f'Slate submitted ({commit}). The backup job is pending.')
                else:
                    st.info('These exact slate inputs are already in the private archive queue.')
