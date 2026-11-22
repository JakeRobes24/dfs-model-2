"""Owner-only slate archive controls."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from history_intake import MAX_PACKET, make_submission, submit_reviewed_slate
from history_panel import NOV20_BACKFILL, NOV20_ORIGINAL, owner_can_view_history
from slate_replay_capture import capture_pool
from slate_research import games_for_date

PRODUCTION_CALLBACK = 'https://dfs-model-2-d9e8r22wzuea8frj2jpxxo.streamlit.app/oauth2callback'


def _intake_token():
    token = os.environ.get('DFS_HISTORY_INTAKE_TOKEN', '').strip()
    if token:
        return token
    try:
        redirect = st.secrets['auth']['redirect_uri']
    except (KeyError, StreamlitSecretNotFoundError):
        return ''
    snapshot = (os.environ.get('DFS_HISTORY_SNAPSHOT_URL'), os.environ.get('DFS_HISTORY_SNAPSHOT_SHA256'))
    if redirect == PRODUCTION_CALLBACK and snapshot in (NOV20_ORIGINAL, NOV20_BACKFILL):
        return os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN', '').strip()
    return ''


def render_slate_archive(pool, *, slate_date=None, generated_lineups=None, replay_inputs=None, market_events=()):
    owner = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
    if not owner or not owner_can_view_history(owner, st.user):
        return
    token = _intake_token()
    if not token:
        return

    with st.expander('Save reviewed slate to private history'):
        st.caption('Saves the current full pool and projections. Include verified actuals or a final lineup CSV when available.')
        if replay_inputs is not None:
            st.caption('This save also records the capture time, scheduled tip coverage and reviewed source timestamps.')
        if market_events:
            st.caption('Fresh matched player props are included when the game is verified pre-tip at save time.')
        with st.form('history_intake'):
            slate = slate_date
            if slate is None:
                slate = st.date_input('Slate date (ET)', datetime.now(ZoneInfo('America/New_York')).date())
            else:
                st.caption(f'Slate date (ET) · {slate:%b %d, %Y}')
            actual = st.file_uploader('Verified actuals CSV (optional)', type='csv')
            lineups = st.file_uploader('Final lineups CSV (optional)', type='csv')
            use_generated = (generated_lineups is not None and not generated_lineups.empty
                             and st.checkbox('Include the four lineups shown above.', value=True))
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
                if use_generated and 'lineups' not in optional:
                    optional['lineups'] = generated_lineups.to_csv(index=False)
                path, raw = make_submission(pool, slate, **optional)
                if replay_inputs is not None:
                    audit, input_hashes = replay_inputs
                    retry_key = (path, input_hashes, audit.to_csv(index=False), market_events)
                    previous = st.session_state.get('history_replay_retry')
                    if previous is None or previous[0] != retry_key:
                        captured_at = datetime.now(timezone.utc)
                        try:
                            schedule = games_for_date(slate)
                        except (OSError, ValueError, KeyError, TypeError, AttributeError):
                            schedule = []
                        archived = capture_pool(pool, audit, schedule, slate, captured_at, input_hashes,
                                                market_events=market_events)
                        path, raw = make_submission(archived, slate, **optional)
                        st.session_state['history_replay_retry'] = (retry_key, path, raw)
                    else:
                        _, path, raw = previous
                commit = submit_reviewed_slate(token, path, raw)
            except (ValueError, OSError) as error:
                st.error(str(error))
            else:
                if commit:
                    st.success(f'Slate submitted ({commit}). The backup job is pending.')
                else:
                    st.info('These exact slate inputs are already in the private archive queue.')
