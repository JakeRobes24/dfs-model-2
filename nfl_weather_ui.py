"""Read-only weather evidence capture for NFL staging."""
import json

import pandas as pd
import streamlit as st

from nfl_weather import collect_nfl_weather


def render_nfl_weather(audit):
    """Keep weather receipts associated with the exact uploaded contest."""
    with st.expander('Pre-lock venue and weather review', expanded=True):
        st.caption('Use the contest’s Eastern date. If your decision deadline is earlier than the first game, enter it here.')
        slate = st.date_input('Weather slate date (ET)', value=None, key='nfl_weather_date')
        cutoff = st.text_input('Earlier decision deadline (optional, ISO 8601 with timezone)',
                               key='nfl_weather_cutoff').strip()
        run = st.button('Check venue and weather', key='nfl_weather_check', disabled=slate is None)
        scope = (audit['contest_sha256'], slate, cutoff)
        if run:
            try:
                with st.spinner('Checking the contest schedule and stadium forecasts…'):
                    receipt = collect_nfl_weather(audit, slate.isoformat(), cutoff_utc=cutoff)
            except ValueError as error:
                st.error(str(error))
                st.session_state.pop('nfl_weather_receipt', None)
            else:
                st.session_state['nfl_weather_receipt'] = scope, receipt
        saved = st.session_state.get('nfl_weather_receipt')
        if saved is None or saved[0] != scope:
            st.info('Weather review pending for this contest.')
            return
        receipt = saved[1]
        st.caption(f"Schedule checked {receipt['schedule_observed_at']}. Refresh before your decision deadline.")
        st.caption('Review passing efficiency, kicking and game script when wind or precipitation is flagged.')
        st.dataframe(pd.DataFrame([
            {'Game': row['game'], 'Venue': row.get('venue'), 'Status': row['status'],
             'Review flags': ', '.join(row.get('review_flags', []))}
            for row in receipt['games']
        ]), hide_index=True)
        for row in receipt['games']:
            if row['hours']:
                st.write(row['game'])
                st.dataframe(pd.DataFrame(row['hours']), hide_index=True)
        st.download_button('Download weather evidence', json.dumps(receipt, indent=2),
                           file_name=f"{audit['contest_id']}-weather.json", mime='application/json')
