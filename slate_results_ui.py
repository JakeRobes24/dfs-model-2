"""Owner-only post-slate review of saved contest versions."""
import os
from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from history_intake import MAX_PACKET, list_slate_packets, load_slate_packet, make_submission, submit_reviewed_slate
from history_intake_ui import _intake_token
from history_panel import owner_can_view_history, render_history_panel
from market_evidence import review_player_props, summarize_player_props
from nba_ownership import OWNERSHIP_FIELDS, compare_ownership
from nba_projection_review import compare_adjustment_methods, compare_frozen_projections
from nba_player_decision_audit import audit_player_decisions, summarize_player_decisions
from slate_import import game_code, matchup_key
from slate_replay_capture import build_replay_rows
from slate_research import ET
from slate_results import SOURCE_ERRORS, collect_final_boxes, compare_results


@st.cache_data(ttl=300, max_entries=12, show_spinner=False)
def public_final_boxes(day, matchups):
    return collect_final_boxes(day, matchups)


def recorded_scores(history, slate):
    if history is None or history.empty:
        return {}
    rows = history.loc[history.slate_date.eq(slate.isoformat()), ['fanduel_id', 'actual_fd_points']]
    scores = rows.dropna().drop_duplicates()
    return scores.loc[~scores.fanduel_id.duplicated(keep=False)].set_index('fanduel_id').actual_fd_points


def lineup_review(lineups, results):
    if lineups is None or not {'lineup', 'fanduel_id'} <= set(lineups):
        return pd.DataFrame()
    joined = lineups[['lineup', 'fanduel_id']].merge(results, on='fanduel_id', how='left', validate='many_to_one')
    joined['result_for_total'] = joined.nba_fd_points.where(joined.outcome.eq('Played')).mask(
        joined.outcome.eq('Did not play'), 0)
    scores = []
    for label, players in joined.groupby('lineup', sort=False):
        if len(players) != 9 or players.fanduel_id.nunique() != 9:
            continue
        daily = players.projected_fd_points.sum(min_count=9)
        adjusted = players.adjusted_fd_points.sum(min_count=9)
        actual = players.result_for_total.sum(min_count=9)
        paired = pd.notna(daily) and pd.notna(adjusted) and pd.notna(actual)
        scores.append({
            'Lineup': label,
            'DAILY projection': daily,
            'Pre-lock projection': adjusted,
            'NBA box-score FD': actual,
            'DAILY absolute error': abs(daily - actual) if paired else None,
            'Pre-lock absolute error': abs(adjusted - actual) if paired else None,
            'Players still unresolved': int(players.result_for_total.isna().sum()),
        })
    return pd.DataFrame(scores)


def new_actuals(results, history, slate):
    """Preserve any prior result, including incomplete rows and disagreements."""
    recorded = history.loc[history.slate_date.eq(slate.isoformat()) &
                           history[['actual_minutes', 'actual_fd_points']].notna().any(axis=1), 'fanduel_id']
    verified = results.outcome.isin(['Played', 'Did not play']) & results.nba_source.ne('')
    fresh = results.loc[verified & ~results.fanduel_id.isin(recorded),
                        ['fanduel_id', 'nba_actual_minutes', 'nba_fd_points', 'nba_source', 'outcome']].copy()
    dnp = fresh.outcome.eq('Did not play')
    fresh.loc[dnp, ['nba_actual_minutes', 'nba_fd_points']] = 0
    fresh['actuals_source'] = 'NBA box-score calculation: ' + fresh.nba_source
    fresh.loc[dnp, 'actuals_source'] = 'NBA confirmed did not play: ' + fresh.loc[dnp, 'nba_source']
    fresh = fresh.rename(columns={'nba_actual_minutes': 'actual_minutes', 'nba_fd_points': 'actual_fd_points'})
    return fresh[['fanduel_id', 'actual_minutes', 'actual_fd_points', 'actuals_source']]


def render_actuals_save(results, history, slate, pool, lineups, token):
    if not token or history is None or history.empty:
        return
    fresh = new_actuals(results, history, slate)
    if fresh.empty:
        return
    st.caption(f'{len(fresh)} newly verified NBA results can be added to private history. Existing results are preserved.')
    if st.button('Save reviewed NBA results and start backup', type='primary'):
        try:
            path, raw = make_submission(pool, slate, actuals=fresh.to_csv(index=False),
                                        lineups=lineups.to_csv(index=False) if lineups is not None else None)
            commit = submit_reviewed_slate(token, path, raw)
        except (ValueError, OSError) as error:
            st.error(str(error))
        else:
            st.success(f'Submitted for backup ({commit}).' if commit else 'These exact results were already submitted.')


def render_post_slate():
    st.header('Review a completed slate')
    history = render_history_panel()
    owner = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
    token = (os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN') or os.environ.get('DFS_HISTORY_INTAKE_TOKEN', '')).strip()
    if not owner or not token or not owner_can_view_history(owner, st.user):
        st.info('Sign in with the authorized account to review saved slates.')
        return

    with st.expander('Multi-slate experimental projection evaluation'):
        st.caption('Compare fixed shadow policies over up to five earlier saved dates. Dates through November 24, 2026 are exploratory; subsequent dates form prospective evidence. No scoring changes are made.')
        if st.button('Evaluate earlier verified slates', key='shadow_multislate_review'):
            from nba_archive_training import load_prior_replays
            from nba_shadow_multislate import compare_across_slates
            try:
                with st.spinner('Checking prior frozen pools and final NBA results…'):
                    earlier, coverage = load_prior_replays(history, datetime.now(ET).date(), token, limit=5)
                st.dataframe(coverage, hide_index=True)
                details, aggregate = compare_across_slates(earlier)
                if aggregate.empty:
                    st.info('No verified earlier replay available.')
                else:
                    st.dataframe(aggregate.round(2), hide_index=True)
                    st.caption('Each policy has its own paired sample. Both player-weighted and equal-date improvements are reported; neither automatically approves a scoring change.')
                    st.dataframe(details.round(2), hide_index=True)
                    st.download_button('Download multi-slate policy evaluation', aggregate.to_csv(index=False),
                                       'shadow_multislate_summary.csv', mime='text/csv')
            except SOURCE_ERRORS:
                st.warning('Multi-slate evidence could not be verified. No policy was changed.')

    with st.expander('Multi-slate candidate selection evaluation'):
        st.caption('Compare two fixed four-entry selection policies from the same eight legal candidates on up to eight earlier dates. Training uses at most five strictly earlier available dates. Bounded solves may skip dates; every skip is shown.')
        if st.button('Evaluate tournament candidate policies', key='portfolio_walkforward'):
            from nba_archive_training import load_prior_replays
            from nba_portfolio_walkforward import walk_forward_portfolios
            try:
                with st.spinner('Checking saved captures and evaluating chronological candidate policies…'):
                    earlier, archive_coverage, captures = load_prior_replays(
                        history, datetime.now(ET).date(), token, limit=8, include_captures=True)
                    detail, aggregate, evaluation_coverage = walk_forward_portfolios(captures, earlier)
                st.dataframe(archive_coverage, hide_index=True)
                if not evaluation_coverage.empty:
                    st.dataframe(evaluation_coverage, hide_index=True)
                if aggregate.empty:
                    st.info('No completed paired portfolio evaluations.')
                else:
                    st.caption('Differences are simulation minus projection in actual FanDuel points; dates receive equal weight. These are not contest ranks, profits or evidence of a validated edge.')
                    st.dataframe(aggregate.round(2), hide_index=True)
                    st.dataframe(detail.round(2), hide_index=True)
                    st.download_button('Download tournament policy evaluation', detail.to_csv(index=False),
                                       'portfolio_walkforward.csv', mime='text/csv')
            except SOURCE_ERRORS:
                st.warning('The historical tournament evaluation could not be verified.')

    available = {}
    if history is not None and not history.empty:
        rows = history[['slate_date', 'fanduel_id']].drop_duplicates()
        for day, group in rows.groupby('slate_date'):
            prefixes = group.fanduel_id.astype(str).str.extract(r'^([0-9]{1,12})-\d+$', expand=False)
            available[day] = sorted(prefixes.dropna().unique())
    today = datetime.now(ET).date()
    days = sorted((day for day, contests in available.items() if contests and day <= today.isoformat()), reverse=True)
    choice = st.selectbox('Saved slate date (ET)', ['Choose a date', *days, 'Other date'])
    if choice == 'Choose a date':
        return
    if choice == 'Other date':
        slate = st.date_input('Slate date (ET)', today, max_value=today, key='results_date')
    else:
        slate = datetime.fromisoformat(choice).date()
    contests = available.get(slate.isoformat(), [])
    contest = st.selectbox('FanDuel contest', contests + ['Other contest'], key=f'results_contest_{slate}')
    if contest == 'Other contest':
        contest = st.text_input('FanDuel contest ID', max_chars=12).strip()
        if not contest:
            return

    try:
        commit, folder, versions = list_slate_packets(token, slate, contest)
        if not versions:
            st.info('This contest has no full saved pool in the archive. Save the reviewed pool under Build a slate first.')
            return
        version = versions[0]
        if len(versions) > 1:
            version = st.selectbox('Saved version', versions, index=None,
                                   format_func=lambda value: value[:12], key=f'results_version_{slate}_{contest}')
            st.caption('Choose the version that contains the reviewed projections and lineups you want to compare.')
            if version is None:
                return
        pool, lineups = load_slate_packet(token, commit, folder, version)
    except SOURCE_ERRORS:
        st.warning('The saved slate could not be loaded or verified.')
        return

    games = tuple(sorted({matchup_key(game_code(value)) for value in pool.game} - {''}))
    try:
        with st.spinner('Checking final NBA box scores…'):
            boxes = public_final_boxes(slate, games)
            results, finals = compare_results(pool, slate, boxes, recorded_scores(history, slate))
    except SOURCE_ERRORS:
        st.warning('NBA final results are temporarily unavailable. Try this slate again shortly.')
        return

    st.caption(f'Contest {contest} · {len(finals)}/{len(games)} final box scores · saved version {version[:12]}')
    played = results.outcome.eq('Played')
    dnp = results.outcome.eq('Did not play')
    missing = len(results) - int(played.sum()) - int(dnp.sum())
    st.write(f'**{int(played.sum())} played · {int(dnp.sum())} did not play · {missing} unresolved**')
    disagreements = results.actual_comparison.eq('Differs')
    if disagreements.any():
        st.warning(f'{int(disagreements.sum())} NBA-calculated results differ from recorded results. Both values are preserved.')
    st.caption('NBA box-score points use FanDuel scoring weights. Recorded contest scores are shown separately when available.')
    render_actuals_save(results, history, slate, pool, lineups, _intake_token())
    summary = lineup_review(lineups, results)
    if not summary.empty:
        st.subheader('Saved lineups')
        st.caption('Each row compares the two forecasts for the same nine players. Errors appear once both forecasts '
                   'and all results are available. A confirmed did-not-play result contributes zero.')
        st.dataframe(summary.round(2), hide_index=True)
    if lineups is not None and not lineups.empty and set(finals) == set(games):
        with st.expander('Historical contest-field comparison'):
            st.caption('Optional reviewed entry sample from one contest. Use anonymous entry IDs, field_id, source, slot and fanduel_id. Include both UTIL rows. This compares only supplied entries and cannot authenticate the sample or infer official ranks or prizes.')
            field_file = st.file_uploader('Historical contest entries CSV', type='csv',
                                          key=f'field_entries_{slate}_{contest}_{version[:12]}')
            if field_file is not None:
                try:
                    from nba_historical_field import review_supplied_field
                    if field_file.size > MAX_PACKET:
                        raise ValueError('Use a field sample smaller than 8 MiB.')
                    field = pd.read_csv(StringIO(field_file.getvalue().decode('utf-8-sig')), dtype=str)
                    field_summary, field_exposure = review_supplied_field(pool, lineups, field, results)
                    st.dataframe(field_summary.round(2), hide_index=True)
                    st.caption('Repeated player sets with distinct entry IDs are counted separately. Ownership below applies only to the supplied entries.')
                    st.download_button('Download sample field ownership', field_exposure.to_csv(index=False),
                                       f'{slate}_{contest}_sample_field_ownership.csv', mime='text/csv')
                except (ValueError, TypeError, KeyError, pd.errors.ParserError) as exc:
                    st.warning(f'Field comparison unavailable: {exc}')
    flags = results.loc[~(played | dnp) | disagreements]
    if not flags.empty:
        st.subheader('Results to review')
        st.dataframe(flags, hide_index=True)
    gaps = results.loc[played & results.projected_fd_points.isna()].sort_values('nba_fd_points', ascending=False)
    with st.expander(f'Played without a DAILY projection · {len(gaps)}'):
        st.dataframe(gaps[['fanduel_name', 'team', 'nba_actual_minutes', 'nba_fd_points', 'nba_source']], hide_index=True)
    with st.expander(f'Full audit · {len(results)} players'):
        st.dataframe(results, hide_index=True)
    st.download_button('Download post-slate audit', results.to_csv(index=False),
                       f'{slate}_{contest}_post_slate_audit.csv', mime='text/csv')

    with st.expander('Pre-lock replay data'):
        try:
            replay = build_replay_rows(pool, results, slate)
        except ValueError as exc:
            st.info(str(exc))
        else:
            resolved = replay.verified_outcome.ne('needs_review')
            st.caption(f'{int(resolved.sum())}/{len(replay)} verified outcomes. The export keeps the full archived player pool.')
            st.caption('Both models use the same eligible players with verified outcomes. Confirmed DNPs score zero for points. Minutes use players who played.')
            if len(finals) != len(games):
                st.info('Some games are pending. These errors cover currently verified results.')
            errors = compare_frozen_projections(replay)
            st.dataframe(errors.round(2), hide_index=True)
            from nba_shadow_research import compare_shadow_forecasts
            if len(finals) == len(games):
                shadow = compare_shadow_forecasts(replay)
                if not shadow.empty:
                    st.caption('Exploratory fixed policies, compared on identical supported played-player rows. No scoring weights are changed. Coverage differs between policies; single-slate results do not validate a policy.')
                    st.dataframe(shadow.round(2), hide_index=True)
                    st.download_button('Download experimental research comparison', shadow.to_csv(index=False),
                                       f'{slate}_{contest}_{version[:12]}_shadow_research.csv', mime='text/csv')
                else:
                    st.caption('This capture predates the frozen research features; experimental comparisons are unavailable.')
            if len(finals) == len(games):
                st.caption('Experimental equal-entry comparison: generate eight legal projection-ranked candidates from the saved pool, then select four by projected mean or simulated P90. Training uses earlier verified frozen results only; current actuals are used only for scoring.')
                if st.button('Compare candidate selection policies', key=f'candidate_experiment_{slate}_{contest}_{version[:12]}'):
                    from nba_archive_training import load_prior_replays
                    from nba_candidate_experiment import build_experiment, score_experiment
                    try:
                        with st.spinner('Checking earlier training and rebuilding frozen candidates…'):
                            training, coverage = load_prior_replays(history, slate, token, limit=5)
                            st.dataframe(coverage, hide_index=True)
                            if training.empty:
                                raise ValueError('No earlier verified frozen training captures.')
                            candidates, ranges, selections, count = build_experiment(pool, training, slate)
                            policy_report, actual_totals = score_experiment(pool, candidates, selections, results, slate)
                        st.caption(f'{count} earlier played training rows. No changes to live optimizer rankings; this is a fixed historical candidate-ranking experiment, not a contest win-rate estimate.')
                        st.dataframe(policy_report.round(2), hide_index=True)
                        st.dataframe(ranges.merge(actual_totals, on='lineup', validate='one_to_one').round(2), hide_index=True)
                        st.download_button('Download candidate policy comparison', policy_report.to_csv(index=False),
                                           f'{slate}_{contest}_candidate_policy_comparison.csv', mime='text/csv')
                    except (ValueError, TypeError, KeyError, OSError) as exc:
                        st.info(f'Candidate policy comparison unavailable: {exc}')
            decisions = audit_player_decisions(replay)
            decision_summary = summarize_player_decisions(decisions)
            st.caption('Player-by-player projection changes, error improvements and regressions. '
                       'Unresolved outcomes are not scored; confirmed DNPs contribute zero points.')
            st.dataframe(decision_summary.round(2), hide_index=True)
            with st.expander(f'Player decision audit · {len(decisions)} eligible players'):
                st.dataframe(decisions.round(2), hide_index=True)
            st.download_button('Download player decision audit', decisions.to_csv(index=False),
                               f'{slate}_{contest}_{version[:12]}_player_decisions.csv', mime='text/csv')
            methods = compare_adjustment_methods(replay)
            if not methods.empty:
                st.caption('Error by recorded method among changed projections.')
                st.dataframe(methods.round(2), hide_index=True)
            props = review_player_props(replay, results)
            if not props.empty:
                st.caption('Player props are scored as sportsbook thresholds against official stats. Pushes are excluded '
                           'from probability error. Several books may quote the same player.')
                prop_summary = summarize_player_props(props)
                if not prop_summary.empty:
                    st.caption('The paired comparison counts each player once per stat and uses the median threshold across books.')
                    st.dataframe(prop_summary.round(2), hide_index=True)
                st.download_button('Download player prop review', props.to_csv(index=False),
                                   f'{slate}_{contest}_{version[:12]}_player_props.csv', mime='text/csv')
            st.download_button('Download frozen replay data', replay.to_csv(index=False),
                               f'{slate}_{contest}_{version[:12]}_frozen_replay.csv', mime='text/csv')

            if set(OWNERSHIP_FIELDS) <= set(replay):
                st.caption('Compare the slate-level forecast with reviewed ownership from one specific contest field.')
                st.caption('CSV columns are fanduel_id, field_id, actual_ownership_pct, and source.')
                ownership = st.file_uploader('Reviewed contest ownership CSV (optional)', type='csv',
                                             key=f'ownership_{slate}_{contest}_{version[:12]}')
                if ownership is not None:
                    try:
                        if ownership.size > MAX_PACKET:
                            raise ValueError('Use an ownership file smaller than 8 MiB.')
                        actual = pd.read_csv(StringIO(ownership.getvalue().decode('utf-8-sig')), dtype=str)
                        comparison = compare_ownership(replay, actual)
                    except (ValueError, pd.errors.ParserError) as exc:
                        st.warning(str(exc))
                    else:
                        if comparison.empty:
                            st.info('No archived projections matched the supplied ownership rows.')
                        else:
                            mae = comparison.error_pp.abs().mean()
                            st.caption(f'{len(comparison)}/{len(actual)} supplied players matched · {mae:.1f} percentage points mean absolute error.')
                            st.dataframe(comparison, hide_index=True)
                            st.download_button('Download ownership comparison', comparison.to_csv(index=False),
                                               f'{slate}_{contest}_{version[:12]}_ownership.csv', mime='text/csv')
