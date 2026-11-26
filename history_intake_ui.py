"""Owner-only slate archive controls."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from history_intake import MAX_PACKET, make_submission, submit_reviewed_slate, check_recovery_receipt
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

    # Explicit owner opt-in; never submit actuals or historical reconstructions automatically.
    if replay_inputs is not None and slate_date == datetime.now(ZoneInfo('America/New_York')).date():
        auto = st.checkbox('Automatically preserve reviewed pre-tip candidates in private history',
                           value=False, key='history_auto_capture')
        if auto and generated_lineups is not None and not generated_lineups.empty:
            try:
                audit, input_hashes = replay_inputs
                lineup_csv = generated_lineups.to_csv(index=False)
                base_path, _ = make_submission(pool, slate_date, lineups=lineup_csv)
                from hashlib import sha256
                fingerprint = sha256(repr((base_path, input_hashes, audit.to_csv(index=False),
                                           market_events)).encode()).hexdigest()
                saved = st.session_state.get('history_auto_saved', set())
                if fingerprint not in saved:
                    pending = st.session_state.get('history_auto_pending', {})
                    packet = pending.get(fingerprint)
                    if packet is None:
                        schedule = games_for_date(slate_date)
                        archived = capture_pool(pool, audit, schedule, slate_date, datetime.now(timezone.utc),
                                                input_hashes, market_events=market_events)
                        if archived.replay_before_full_slate_tip.all():
                            packet = make_submission(archived, slate_date, lineups=lineup_csv)
                            st.session_state['history_auto_pending'] = {fingerprint: packet}
                    if packet is None:
                        st.info('Automatic preservation skipped: full-slate pre-tip timing is not verified.')
                    else:
                        path, raw = packet
                        commit = submit_reviewed_slate(token, path, raw)
                        st.session_state['history_auto_saved'] = saved | {fingerprint}
                        st.session_state.pop('history_auto_pending', None)
                        st.success('Reviewed pre-tip candidates submitted to private history; backup verification is separate.')
                else:
                    st.caption('Unchanged reviewed candidates already submitted this session.')
            except (ValueError, OSError, KeyError, TypeError, AttributeError):
                st.warning('Automatic preservation unavailable. Use the manual archive controls below.')

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
            prepare = st.form_submit_button('Prepare downloadable archive packet', key='history_intake_prepare')
            save = st.form_submit_button('Save slate and start backup', key='history_intake_save')
        if prepare or save:
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
                # Retain exact bytes before any network write. A download survives a
                # session reset; session_state alone does not.
                st.session_state['history_prepared_packet'] = (path, raw)
                if save:
                    commit = submit_reviewed_slate(token, path, raw)
                    st.session_state['history_packet_receipt'] = (path, commit)
                else:
                    st.success('Packet prepared locally. Download it before submitting. Nothing uploaded.')
            except (ValueError, OSError) as error:
                st.error(str(error))
            else:
                if save:
                    if commit:
                        st.success(f'Exact slate packet verified in the archive ({commit}). Backup publication is separate.')
                    else:
                        st.info('These exact slate inputs are already in the private archive queue.')
        prepared = st.session_state.get('history_prepared_packet')
        if prepared is not None:
            path, raw = prepared
            st.caption(f'Last prepared packet: {path}. This may be from an earlier review; prepare again after changes.')
            st.download_button('Download exact prepared archive packet',raw,
                               file_name=path.rsplit('/',1)[-1],mime='application/json',
                               key='history_packet_download',on_click='ignore')
            receipt=st.session_state.get('history_packet_receipt')
            if receipt is not None and receipt[0]==path:
                st.caption('Archive packet verified by readback. Backup publication is separate.')


def render_archive_receipt_check():
    """Owner can verify downloaded packet after a browser session reset, without a slate upload."""
    owner=os.environ.get('DFS_HISTORY_OWNER_EMAIL','').strip()
    if not owner or not owner_can_view_history(owner,st.user):
        return
    token=(os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN','').strip() or _intake_token())
    if not token:
        return
    with st.expander('Check a saved archive receipt'):
        st.caption('Use a downloaded exact archive packet. Checks remote bytes only; does not upload, certify timing or verify backup publication.')
        file=st.file_uploader('Previously downloaded archive packet',type='json',key='history_receipt_packet')
        if file is not None and st.button('Verify archive receipt',key='history_receipt_verify'):
            try:
                if file.size>MAX_PACKET:
                    raise ValueError('Archive packet exceeds 8 MiB.')
                receipt=check_recovery_receipt(token,file.getvalue())
            except (ValueError,OSError,KeyError,TypeError,AttributeError):
                st.warning('Receipt could not be verified. No submission attempted.')
            else:
                if receipt['status']=='verified':
                    st.success(f"Exact archive packet verified at {receipt['commit'][:12]}. Backup publication is separate.")
                else:
                    st.warning('Exact packet not found at the checked archive revision. Keep your local copy.')
                st.caption(receipt['path'])

