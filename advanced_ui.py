"""Preserved historical experiments and advanced upload workflows."""
from history_intake_ui import render_slate_archive
import streamlit as st
import pandas as pd
from model import consensus,optimize
from slate_tools_ui import review_prelock, render_challenger
from evidence import validate_sources,evaluate_minutes,scenario_projections
from calibration import audit_actuals,evaluate_bias_correction
from research_integration import prepare_research_pool, optimize_research, lineup_summary
from research_upgrade import compare_scenarios
from pathlib import Path


def render_advanced():
    st.subheader('November 20 research-integrated optimization')
    st.caption('This tab uses the 247-player cumulative research file, with historical evidence, independent minutes, injury snapshot, and explicitly labeled tentative projections. It does not auto-verify live news.')
    research_upload=st.file_uploader('Optional replacement cumulative research CSV',type='csv',key='research_upload')
    bundled=Path(__file__).parent/'data'/'nov20_research_v33_full.csv'
    if research_upload is not None or bundled.exists():
        try:
            research=pd.read_csv(research_upload if research_upload is not None else bundled,low_memory=False)
            col='v33_tentative_fd_for_comparison'
            left,right=st.columns(2)
            exclude_q=left.checkbox('Exclude questionable players (morning report)',True,key='research_q')
            exclude_h=right.checkbox('Exclude Kevin Huerter for comparison',True,key='research_h')
            overlap_r=st.slider('Maximum overlap — research lineups',4,8,7,key='research_overlap')
            pool=prepare_research_pool(research,projection_column=col,exclude_questionable=exclude_q,exclude_huerter=exclude_h)
            stats=st.columns(4)
            stats[0].metric('Research rows',len(pool))
            stats[1].metric('Historical L5 coverage',int(pool.historical_l5_fd.notna().sum()))
            stats[2].metric('Excluded by status/choice',int((~pool.eligible).sum()))
            stats[3].metric('Missing scenario scores',int(pool.adjusted_fd_points.isna().sum()))
            st.dataframe(pool[['fanduel_name','salary','official_status_snapshot','projected_fd_points','adjusted_fd_points','historical_l5_fd','historical_l10_fd','historical_l5_minutes','minutes_disagreement','confidence','projection_warning']],use_container_width=True,hide_index=True)
            st.download_button('Download 247-player research model input',pool.to_csv(index=False).encode(),'nov20_research_optimizer_input.csv')
            if st.button('Optimize four lineups from research',key='research_opt'):
                lineups=__import__('model').optimize(pool,number=4,max_overlap=overlap_r)
                if lineups.empty:st.error('No legal four-lineup portfolio under current filters.')
                else:
                    st.dataframe(lineup_summary(lineups),hide_index=True,use_container_width=True)
                    for k,g in lineups.groupby('lineup'):
                        st.markdown(f'**Lineup {k} — ${g.salary.sum():,} — {g.adjusted_fd_points.sum():.1f} scenario FD**')
                        st.dataframe(g[['slot','player','salary','adjusted_fd_points','confidence']],hide_index=True,use_container_width=True)
                    st.download_button('Save pre-news lineups and model projections',lineups.to_csv(index=False).encode(),'nov20_research_model_lineups.csv')
            st.subheader('Model 2.0 — baseline vs uncertainty vs historical-upside sensitivity')
            st.caption('Upward historical scoring evidence is used only as a capped sensitivity proxy, never as a calibrated ceiling. Ownership/correlation are not estimated.')
            if st.button('Compare all three research scenarios and save four lineups each',key='research_scenarios'):
                scenario_inputs,scenario_lineups=compare_scenarios(research,max_overlap=overlap_r,exclude_questionable=exclude_q,exclude_huerter=exclude_h)
                for mode,g in scenario_lineups.groupby('scenario',sort=False):
                    st.markdown(f'**{mode}**')
                    st.dataframe(lineup_summary(g),hide_index=True,use_container_width=True)
                    for k,team in g.groupby('lineup'):
                        with st.expander(f'{mode} lineup {k} — ${team.salary.sum():,} — {team.adjusted_fd_points.sum():.1f} sensitivity FD'):
                            st.dataframe(team[['slot','player','salary','adjusted_fd_points','confidence']],hide_index=True)
                st.download_button('Download scenario comparison lineups',scenario_lineups.to_csv(index=False).encode(),'nov20_scenario_lineups.csv',key='download_scenario_lineups')
                st.download_button('Download full research scoring inputs',scenario_inputs.to_csv(index=False).encode(),'nov20_scenario_inputs.csv',key='download_scenario_inputs')
                st.download_button('Save pre-news model snapshot',scenario_lineups.to_csv(index=False).encode(),'nov20_pre_news_model_snapshot.csv',key='download_snapshot')
            st.warning('Morning injury statuses, third-party historical data and tentative projections are NOT live confirmed starters or final projections. Review every uncertain player before lock.')
        except Exception as exc:st.exception(exc)
    else:
        st.info('Upload the cumulative research CSV to use the research-integrated optimizer.')
    st.divider()

    base=st.file_uploader('Upload reconciled contest + DAILY CSV',type='csv',key='base')
    sources=st.file_uploader('Upload independent minutes estimates (optional)',type='csv',key='sources')
    history=st.file_uploader('Upload historical minutes (optional)',type='csv',key='history')
    st.markdown('**Independent source CSV columns:** `player,source,minutes,independent_group,observed_at` (last two optional).  **History CSV:** `player,season_mpg,last5_mpg,last10_mpg`.')
    if base:
        try:
            b=pd.read_csv(base, dtype={'fanduel_id': str});required={'fanduel_id','fanduel_name','salary','roster_eligibility','injury_flag','projected_minutes','projected_fd_points'}
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
            d=review_prelock(d)
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
            render_challenger(d, exclude_uncertain=exclude)
            if st.button('Optimize four lineups',key='base_opt'):
                lineups=optimize(d,number=4,max_overlap=overlap,exclude_uncertain=exclude)
                if lineups.empty:st.error('No legal lineup found for these inputs')
                else:
                    for num,g in lineups.groupby('lineup'):
                        st.markdown(f'**Lineup {num}: ${g.salary.sum():,} | {g.adjusted_fd_points.sum():.1f} scenario FD points | {sum(g.confidence=="low")} low-confidence players**')
                        st.dataframe(g,use_container_width=True,hide_index=True)
                    st.download_button('Download lineup candidates',lineups.to_csv(index=False).encode(),'four_lineups.csv','text/csv')
            render_slate_archive(d)
        except Exception as exc:st.exception(exc)
    else:st.info('Upload the reconciled contest CSV to begin. No external data is fetched automatically.')
