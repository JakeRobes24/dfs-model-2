import streamlit as st
import pandas as pd
from model import consensus,optimize
from evidence import validate_sources,evaluate_minutes,scenario_projections
from calibration import audit_actuals,evaluate_bias_correction
st.set_page_config(page_title='DFS Model 2.0 | Consensus',layout='wide')
st.title('DFS Model 2.0 — Minutes & Source Consensus')
st.caption('Evidence-first projections. Missing source evidence is never presented as verified.')
base=st.file_uploader('Upload reconciled contest + DAILY CSV',type='csv',key='base')
sources=st.file_uploader('Upload independent minutes estimates (optional)',type='csv',key='sources')
history=st.file_uploader('Upload historical minutes (optional)',type='csv',key='history')
st.markdown('**Independent source CSV columns:** `player,source,minutes,independent_group,observed_at` (last two optional).  **History CSV:** `player,season_mpg,last5_mpg,last10_mpg`.')
if base:
    try:
        b=pd.read_csv(base);required={'fanduel_id','fanduel_name','salary','roster_eligibility','injury_flag','projected_minutes','projected_fd_points'}
        if not required.issubset(b.columns):st.error(f'Missing columns: {sorted(required-set(b.columns))}');st.stop()
        e=pd.read_csv(sources) if sources else None;h=pd.read_csv(history) if history else None
        d=consensus(b,e,h)
        if e is not None:
            st.subheader('Source evidence quality')
            ev=validate_sources(e)
            st.dataframe(ev[['player','source','minutes','independent_group','valid_minutes','duplicate_group','stale_or_undated']],use_container_width=True,hide_index=True)
            if (~ev.valid_minutes).any():st.warning('Some source minutes are invalid and excluded from consensus.')
        scenario=st.file_uploader('Optional injury/rotation scenario CSV: player,minutes_delta',type='csv',key='scenario')
        if scenario is not None:
            d=scenario_projections(d,pd.read_csv(scenario))
            st.info('Explicit scenario applied; this does not imply the scenario will occur.')
        with st.expander('Post-slate source accuracy (optional)'):
            predictions=st.file_uploader('Upload historical provider predictions CSV: player,source,minutes',type='csv',key='predictions')
            actuals=st.file_uploader('Upload actual game minutes CSV: player,actual_minutes',type='csv',key='actuals')
            if predictions is not None and actuals is not None:
                errors,ranking=evaluate_minutes(pd.read_csv(predictions),pd.read_csv(actuals))
                st.dataframe(ranking,use_container_width=True,hide_index=True)
                st.download_button('Download source accuracy',ranking.to_csv(index=False),'source_accuracy.csv')
                st.caption('Provider rankings are descriptive. Small samples should not drive automatic weights.')
        with st.expander('DAILY historical calibration — actual minutes (optional)'):
            st.caption('Use completed-game actuals only. Same-day results are never used to calibrate pre-lock projections. No automatic correction is applied without validated improvement.')
            actual_history=st.file_uploader('Upload dated actuals tracker: slate_date,fanduel_id,projected_minutes,actual_minutes',type='csv',key='actual_history')
            cutoff=st.text_input('Slate date for leakage-safe cutoff (YYYY-MM-DD)',value='2026-11-20')
            if actual_history is not None:
                hist=pd.read_csv(actual_history)
                cleaned,summary=audit_actuals(hist,as_of_date=cutoff)
                st.write('Historical actuals audit',summary)
                walk,metrics=evaluate_bias_correction(hist,as_of_date=cutoff)
                st.write('Walk-forward comparison',metrics)
                if not walk.empty:
                    st.dataframe(walk,use_container_width=True,hide_index=True)
                    st.download_button('Download walk-forward calibration audit',walk.to_csv(index=False),'walk_forward_calibration.csv')
                if not metrics.get('correction_improves_mae',False):
                    st.warning('Calibration not approved: insufficient history or no demonstrated MAE improvement. Existing projections remain unchanged.')
                else:
                    st.info('Historical correction shows positive walk-forward improvement. This is research evidence, not automatic authorization to alter the live slate.')
        cols=st.columns(4)
        cols[0].metric('Players in reconciliation',len(d));cols[1].metric('With independent sources',int((d.independent_sources>0).sum()));cols[2].metric('Consensus (2+ agreeing)',int(d.minutes_method.eq('independent_source_consensus').sum()));cols[3].metric('DAILY-only',int(d.minutes_method.eq('DAILY_only_unverified').sum()))
        st.dataframe(d[['fanduel_name','salary','injury_flag','projected_minutes','adjusted_minutes','minutes_method','confidence','independent_sources','historical_minutes','adjusted_fd_points','projection_warning']],use_container_width=True)
        st.download_button('Download auditable adjusted projections',d.to_csv(index=False).encode(),'adjusted_projections.csv','text/csv')
        st.subheader('Lineup optimizer')
        st.warning('Low-confidence DAILY-only estimates remain eligible by default, but their projections are not independently validated. Review uncertain players before entry.')
        exclude=st.checkbox('Sensitivity test: exclude low-confidence estimates',False)
        overlap=st.slider('Maximum shared players between lineups',4,8,7)
        if st.button('Optimize four lineups'):
            lineups=optimize(d,number=4,max_overlap=overlap,exclude_uncertain=exclude)
            if lineups.empty:st.error('No legal lineup found for these inputs')
            else:
                for num,g in lineups.groupby('lineup'):
                    st.markdown(f'**Lineup {num}: ${g.salary.sum():,} | {g.adjusted_fd_points.sum():.1f} scenario FD points | {sum(g.confidence=="low")} low-confidence players**')
                    st.dataframe(g,use_container_width=True,hide_index=True)
                st.download_button('Download lineup candidates',lineups.to_csv(index=False).encode(),'four_lineups.csv','text/csv')
    except Exception as exc:st.exception(exc)
else:st.info('Upload the reconciled contest CSV to begin. No external data is fetched automatically.')
