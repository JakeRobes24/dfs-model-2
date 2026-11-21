"""Pre-lock evidence review and full-pool lineup comparisons."""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from lineup_challenger import challenge_lineups
from prelock import apply_prelock


def review_prelock(pool):
    with st.expander('Pre-lock evidence and adjustments'):
        st.caption('Upload reviewed evidence from official injury and lineup reports and independent minutes research. Source records are supplied by your research team.')
        upload = st.file_uploader('Pre-lock evidence CSV', type='csv', key='prelock_evidence')
        if upload is None:
            return pool
        st.caption('Columns: fanduel_id, source, independent_group, observed_at, official, status, starter, role, minutes')
        timestamp = st.text_input(
            'Decision time with UTC offset',
            value=datetime.now(timezone.utc).isoformat(timespec='minutes'),
            key='prelock_as_of',
        )
        try:
            adjusted, audit = apply_prelock(pool, pd.read_csv(upload, dtype={'fanduel_id': str}), timestamp)
        except (ValueError, KeyError) as exc:
            st.error(str(exc))
            st.stop()
        st.dataframe(audit, hide_index=True)
        affected = adjusted.loc[adjusted.prelock_change.ne(''), [
            'fanduel_id', 'fanduel_name', 'prelock_change', 'eligible',
            'prelock_prior_fd_points', 'adjusted_fd_points', 'prelock_sources',
        ]]
        st.dataframe(affected, hide_index=True)
        st.download_button('Download pre-lock pool and adjustments', adjusted.to_csv(index=False),
                           'prelock_pool.csv', key='prelock_pool_download')
        st.download_button('Download pre-lock evidence audit', audit.to_csv(index=False),
                           'prelock_evidence_audit.csv', key='prelock_evidence_download')
        return adjusted


def render_challenger(pool, *, exclude_uncertain=False):
    with st.expander('Full-pool lineup challenger'):
        st.caption('Compare each proposed lineup with the strongest distinct legal alternative. You supply researched ceilings for upside comparisons. Ownership and correlation are outside this comparison.')
        upload = st.file_uploader('Proposed FanDuel lineups CSV', type='csv', key='challenger_proposed')
        if upload is None:
            return
        missing = int((pool.eligible & ~pool.adjusted_fd_points.gt(0)).sum())
        if missing:
            st.warning(f'{missing} contest-eligible players lack a usable positive projection and cannot be optimized.')
        ceiling = st.checkbox('Also compare researched ceiling totals', key='challenger_ceiling')
        if st.button('Challenge lineups', key='challenger_run'):
            try:
                audit, comparison, alternatives = challenge_lineups(
                    pool, pd.read_csv(upload, dtype={'fanduel_id': str}),
                    include_ceiling=ceiling, exclude_uncertain=exclude_uncertain,
                )
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
                return
            st.dataframe(comparison, hide_index=True)
            st.dataframe(audit, hide_index=True)
            if not alternatives.empty:
                st.dataframe(alternatives, hide_index=True)
                st.download_button('Download alternatives', alternatives.to_csv(index=False),
                                   'lineup_alternatives.csv', key='challenger_download')
