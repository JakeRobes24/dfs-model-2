"""Shared Streamlit entry point for production and development preview."""
from datetime import date, datetime, timedelta
from functools import partial
from time import monotonic
from hashlib import sha256
import json
import re

import pandas as pd
import streamlit as st

from advanced_ui import render_advanced
from evidence import validate_sources
from history_intake_ui import render_slate_archive
from history_panel import render_history_panel
from slate_results_ui import render_post_slate
from market_evidence import game_market_evidence, player_market_evidence
from model import SLOTS, allowed_slots, optimize, optimize_late_swap
from nba_ownership import archive_ownership
from opportunity_evidence import opportunity_evidence
from prelock import REQUIRED
from slate_import import matchup_key, reconcile_exports, team_code
from slate_research import (
    ET, FTA_NBA_BOARD, LINEUPEXPERTS_TODAY, compare_reference, fantasysportsedge_reference, games_for_date,
    fta_nba_reference, get_public_research, historical_context, lineupexperts_reference,
    match_public, recent_boxscores, score_slate,
)
from slate_tools_ui import render_challenger


@st.cache_data(ttl=60, max_entries=8, show_spinner=False)
def public_slate_schedule(slate):
    try:
        return games_for_date(slate)
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return []


def started_contest_games(schedule, games, now):
    """Match exact contest games and detect reported starts or elapsed tip times."""
    remaining = {matchup_key(game) for game in games}
    started = set()
    matched = set()
    for entry in schedule:
        away, home = (team_code((entry.get(side) or {}).get('teamTricode', ''))
                      for side in ('awayTeam', 'homeTeam'))
        key = matchup_key(f'{away}@{home}')
        tip = pd.to_datetime(entry.get('gameTimeUtc'), utc=True, errors='coerce')
        if key not in remaining or pd.isna(tip) or tip.tz_convert(ET).date() != now.date():
            continue
        matched.add(key)
        actual = pd.to_datetime(entry.get('actualStartTimeUTC'), utc=True, errors='coerce')
        if tip <= now or entry.get('gameStatus') in (2, 3) or (pd.notna(actual) and actual <= now):
            started.add(key)
    return started, remaining <= matched


@st.cache_data(ttl=300, max_entries=16, show_spinner=False)
def public_research(slate, checked_at):
    # Only public data is cached across sessions. Private history is owner-gated separately.
    return get_public_research(slate, checked_at)


@st.cache_data(ttl=1800, max_entries=16, show_spinner=False)
def public_rotations(slate, games):
    return recent_boxscores(slate, set(games))


@st.cache_data(ttl=1800, max_entries=8, show_spinner=False)
def extended_rotations(slate, games):
    return recent_boxscores(slate, set(games), game_limit=10, days_back=24)


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def public_lineupexperts_reference(slate, today):
    return lineupexperts_reference(slate, today)


@st.cache_data(ttl=300, max_entries=8, show_spinner=False)
def public_fta_reference(slate, as_of, games):
    return fta_nba_reference(slate, as_of, games)


def render_reference_board(scored, rows, stamp, source, context, *, key_prefix=''):
    comparison = compare_reference(scored, rows)
    if comparison.empty:
        st.info(f'{source} has no eligible players matched by name, game and FanDuel salary.')
        return comparison
    st.caption(f'{source} · {stamp:%b %d, %I:%M %p ET} · {len(comparison)} matched. {context}')
    labels = {'fanduel_name': 'Player', 'projected_fd_points': 'DAILY FD',
              'adjusted_fd_points': 'Model FD', 'reference_points': 'Source FD',
              'points_gap': 'Points gap', 'adjusted_minutes': 'Model minutes',
              'reference_minutes': 'Source minutes', 'minutes_gap': 'Minutes gap',
              'reference_ownership': 'Projected ownership %', 'reference_ceiling': 'Simulated 85th percentile',
              'research_check': 'Research check'}
    columns = [key for key in labels if key in comparison]
    flagged = comparison.research_check.str.contains('Missing|Review')
    display = pd.concat([comparison.loc[flagged], comparison.loc[~flagged]])
    st.dataframe(display[columns].rename(columns=labels), hide_index=True)
    st.download_button(f'Download {source} comparison',
                       display.assign(reference_provider=source, source_updated_at=stamp.isoformat())
                       [['fanduel_id', *columns, 'reference_provider', 'source_updated_at']].to_csv(index=False),
                       f"{source.lower().replace(' ', '_')}_comparison.csv", mime='text/csv',
                       key=f'{key_prefix}reference_download_{source}')
    return comparison


def read_optional(upload, required, *, id_column=None):
    if upload is None:
        return None
    if upload.size > 8 * 1024 * 1024:
        raise ValueError('Each slate CSV must be smaller than 8 MiB.')
    frame = pd.read_csv(upload, dtype={id_column: str} if id_column else None)
    missing = set(required) - set(frame)
    if missing:
        raise ValueError(f'{upload.name} is missing: {", ".join(sorted(missing))}.')
    return frame


def manual_inputs(as_of):
    with st.expander('Optional research uploads and optimizer settings'):
        minutes = st.file_uploader('Independent minutes CSV', type='csv', key='slate_manual_minutes')
        history = st.file_uploader('Historical minutes CSV', type='csv', key='slate_manual_history')
        prelock = st.file_uploader('Reviewed pre-lock CSV', type='csv', key='slate_manual_prelock')
        reviewed_points = st.file_uploader('Verified LineupExperts points and optional paired minutes CSV', type='csv', key='slate_reviewed_points')
        st.caption('Optional LineupExperts data requires fanduel_id, points, and observed_at with a timezone. Use a verified source update time. Optional paired_minutes must be from the same published projection, not another minutes site.')
        ceiling = st.file_uploader('Researched GPP ceilings CSV', type='csv', key='slate_manual_ceiling')
        st.caption('For GPP upside, supply fanduel_id and ceiling_fd_points for each optimizable player.')
        st.caption('Minutes: player, source, minutes, observed_at, independent_group (optional). History: player, season_mpg, last5_mpg, last10_mpg.')
        st.caption('Reviewed pre-lock: fanduel_id, source, independent_group, observed_at, official, status, starter, role, minutes.')
        exclude = st.checkbox('Exclude low-confidence players', key='slate_exclude')
        overlap = st.slider('Maximum shared players between lineups', 4, 8, 7, key='slate_overlap')
        try:
            minutes = read_optional(minutes, {'player', 'source', 'minutes', 'observed_at'})
            history = read_optional(history, {'player', 'season_mpg', 'last5_mpg', 'last10_mpg'})
            prelock = read_optional(prelock, REQUIRED, id_column='fanduel_id')
            reviewed_points = read_optional(reviewed_points, {'fanduel_id', 'points', 'observed_at'}, id_column='fanduel_id')
            if reviewed_points is not None:
                if reviewed_points.fanduel_id.duplicated().any() or not reviewed_points.observed_at.astype(str).str.contains(
                    r'(?:Z|[+-][0-9]{2}:[0-9]{2})$', regex=True
                ).all():
                    raise ValueError('Verified LineupExperts rows need unique IDs and an update time with a timezone.')
            ceiling = read_optional(ceiling, {'fanduel_id', 'ceiling_fd_points'}, id_column='fanduel_id')
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            return None
        if minutes is not None:
            audited = validate_sources(minutes.copy())
            published = pd.to_datetime(audited.observed_at, utc=True, errors='coerce', format='mixed')
            good = (audited.valid_minutes & published.between(as_of - timedelta(hours=6), as_of)
                    & audited.source.fillna('').astype(str).str.strip().ne(''))
            if not good.all():
                st.warning(f'{int((~good).sum())} minutes estimates were stale, undated or invalid.')
            minutes = audited.loc[good].assign(observed_at=published[good])
        return minutes, history, prelock, ceiling, exclude, overlap, reviewed_points


def generate_and_challenge(pool, overlap, exclude, objective='adjusted_fd_points', *, time_budget_seconds=None):
    deadline = None if time_budget_seconds is None else monotonic() + time_budget_seconds
    solve = partial(optimize, pool, exclude_uncertain=exclude, objective_column=objective)
    if deadline is None:
        lineups = solve(number=4, max_overlap=overlap)
    else:
        remaining = deadline - monotonic()
        # Reserve up to one solver interval for the leading roster's distinct
        # alternative; unused portfolio time remains available to that solve.
        reserve = min(35.0, max(0.0, remaining) * .20)
        portfolio_budget = remaining - reserve
        lineups = solve(number=4, max_overlap=overlap, time_budget_seconds=portfolio_budget) if portfolio_budget > 0 else pd.DataFrame()
    if lineups.empty:
        return lineups, pd.DataFrame(), pd.DataFrame()
    # Lineup 1 has the best unconstrained objective. A single extra solve finds
    # its best distinct rival. Lineup 1 is itself a distinct rival to every other lineup.
    first = lineups[lineups.lineup.eq(1)]
    if deadline is None:
        alternative = solve(number=1, exclude_rosters=(first.fanduel_id,))
    else:
        remaining = deadline - monotonic()
        alternative = solve(number=1, exclude_rosters=(first.fanduel_id,), time_budget_seconds=remaining) if remaining > 0 else pd.DataFrame()
    scores = pool.set_index('fanduel_id')[objective]
    comparisons = []
    for number, roster in lineups.groupby('lineup'):
        rival = alternative if number == 1 else first
        if rival.empty:
            continue
        comparisons.append({
            'Lineup': number, 'Projected FD': round(roster.adjusted_fd_points.sum(), 2),
            'Best distinct alternative FD': round(rival.adjusted_fd_points.sum(), 2),
            'Alternative minus lineup': round(rival.adjusted_fd_points.sum() - roster.adjusted_fd_points.sum(), 2),
            'Alternative salary': rival.salary.sum(), 'Alternative proven optimal': bool(rival.solver_optimal.all()),
            'Objective edge of alternative': round(scores.loc[rival.fanduel_id].sum() - scores.loc[roster.fanduel_id].sum(), 2),
        })
    return lineups, pd.DataFrame(comparisons), alternative


def show_results(pool, lineups, comparison, alternative):
    from nba_classic_rules import validate_team_roster
    total = 0 if lineups.empty else lineups.lineup.nunique()
    if total < 4:
        st.warning(f'{total} legal lineups found with the current overlap setting and usable projections.')
    if not total:
        return
    for candidate in (lineups, alternative):
        if not candidate.empty:
            for _, roster in candidate.groupby('lineup'):
                validate_team_roster(pool, roster.fanduel_id, require_teams=True)
    status = pool.set_index('fanduel_id')
    if not lineups.solver_optimal.all():
        st.warning('The optimizer reached its time limit for at least one candidate.')
    for number, roster in lineups.groupby('lineup'):
        with st.expander(f'Lineup {number} · {roster.adjusted_fd_points.sum():.1f} FD · ${roster.salary.sum():,}',
                         expanded=number == 1):
            ordered = roster.assign(
                slot_order=roster.slot.map({slot: index for index, slot in enumerate(SLOTS)})
            ).sort_values('slot_order', kind='stable')
            players = []
            for row in ordered.itertuples():
                name = re.sub(r'([\\`*_{}\[\]<>()#|])', r'\\\1', row.player)
                players.append(rf'- **{row.slot}** · {name} · \${row.salary:,} · {row.adjusted_fd_points:.1f} FD')
            st.markdown('\n'.join(players))
            counts = status.loc[roster.fanduel_id, 'team'].value_counts()
            st.caption('Team composition: ' + ' · '.join(f'{team} {count}' for team,count in counts.items()))
            uncertain = status.loc[roster.fanduel_id]
            review = uncertain[(uncertain.confidence.isin(['low', 'missing']))
                               | uncertain.research_attention.str.contains('Availability|disagreement|Role')]
            if len(review):
                st.caption('Review before entry: ' + ', '.join(review.fanduel_name))
    if total and alternative.empty:
        st.warning('The distinct alternative to the leading lineup was not produced; full alternative comparison is incomplete.')
    if not comparison.empty:
        with st.expander('Compare against the full pool'):
            st.caption('Each comparison uses a different legal roster from players with usable projections. Reusing the strongest rival across lineups measures the cost of portfolio overlap.')
            st.dataframe(comparison, hide_index=True)
            if not alternative.empty:
                st.download_button('Download strongest alternative to lineup 1', alternative.to_csv(index=False),
                                   'strongest_alternative.csv')
    from nba_checkpoint_changes import can_reuse_candidates
    verified = can_reuse_candidates((lineups, comparison, alternative))
    if not verified:
        st.warning('Provisional candidates: full portfolio or proven-optimal alternative comparison incomplete. Reassess before entry.')
    st.download_button('Download lineups' if verified else 'Download provisional candidates',
                       lineups.to_csv(index=False), 'four_lineups.csv' if verified else 'provisional_candidates.csv',
                       mime='text/csv')


def render_slate(history_slot):
    st.header('1. Upload your slate')
    st.caption('FanDuel NBA classic · nine unique players · $60,000 cap')
    from slate_upload_session import SlateUpload, select_upload_pair
    # Widget metadata can outlive its uploaded bytes on a rerun. Keep the exact
    # reconciled pair in this user's session, never in a shared Streamlit cache.
    if st.button('Clear slate files and results', key='slate_clear_uploads'):
        for key in ('slate_contest','slate_daily','slate_retained_uploads','slate_results',
                    'last_complete_portfolio','late_swap_result'):
            st.session_state.pop(key, None)
    contest = st.file_uploader('FanDuel contest CSV', type='csv', key='slate_contest')
    daily = st.file_uploader('DAILY projection CSV', type='csv', key='slate_daily')
    now = datetime.now(ET)
    def snapshot(upload):
        if upload is None:
            return None
        data = upload.getvalue()
        if len(data) > 8 * 1024 * 1024:
            raise ValueError('Each slate CSV must be smaller than 8 MiB.')
        return SlateUpload(upload.name, data)
    try:
        incoming = (snapshot(contest), snapshot(daily))
        retained = st.session_state.get('slate_retained_uploads')
        pair, recovered = select_upload_pair(*incoming, retained)
        if pair is None:
            # A changed or invalid partial upload invalidates the old pair;
            # subsequent widget loss must not resurrect the previous slate.
            if retained is not None:
                st.session_state.pop('slate_retained_uploads', None)
            if any(item is not None for item in incoming):
                st.info('Both matching CSV files must be available. A changed or incomplete pair cannot be mixed with earlier inputs.')
            elif retained is None:
                st.caption('Upload both CSVs to begin. If filenames remain visible but research disappears, reload the two files.')
            with history_slot:
                render_history_panel()
            return
        if not recovered and pair != retained:
            st.session_state.pop('slate_retained_uploads', None)
        contest_copy, daily_copy = pair
        contest_bytes, daily_bytes = contest_copy.data, daily_copy.data
        pool, contest_id, extra = reconcile_exports(contest_bytes, daily_bytes)
        st.session_state['slate_retained_uploads'] = pair
        if recovered:
            st.warning('Recovered the last reconciled CSV pair from this session. Check the filenames and contest below; use Clear slate files and results to replace them.')
            st.caption(f'{contest_copy.name} · {daily_copy.name}')
    except (ValueError, OSError, KeyError) as exc:
        st.error(str(exc))
        return
    filename_date = re.search(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)', contest_copy.name)
    suggested_date = now.date()
    if filename_date:
        try:
            suggested_date = date.fromisoformat(filename_date[0])
        except ValueError:
            pass
    latest = now.date() + timedelta(days=1)
    slate = st.date_input('Slate date (ET)', min(suggested_date, latest), max_value=latest,
                          key=f'slate_date_{contest_id}')
    st.write(f'**FanDuel contest {contest_id}** · {slate:%b %d} · {pool.game.nunique()} games · {len(pool)} players')
    with history_slot:
        history = render_history_panel()
    history = history if history is not None else pd.DataFrame()

    st.header('2. Review the player pool')
    refresh = st.button('Refresh all research', key='slate_refresh')
    # Reuse the same freshness window on reruns. A manual refresh is scoped to this session.
    window = now.replace(second=0, microsecond=0, minute=(now.minute // 5) * 5)
    research_scope = (str(contest_id), str(slate), sha256(contest_bytes).hexdigest())
    refresh_key = 'slate_refreshed_at'
    saved_refresh = st.session_state.get(refresh_key)
    if refresh:
        saved_refresh = (research_scope, datetime.now(ET))
        st.session_state[refresh_key] = saved_refresh
    checked_at = max(window, saved_refresh[1]) if isinstance(saved_refresh, tuple) and saved_refresh[0] == research_scope else window
    with st.spinner('Checking official reports, recent rotations and independent projections…'):
        notes, projections, source_status = public_research(slate, checked_at)
        rotations, rotation_status = public_rotations(slate, tuple(sorted(set(pool.game))))
    source_status = [*source_status, ('NBA recent box scores', rotation_status)]
    manual = manual_inputs(now)
    if manual is None:
        return
    minutes, minutes_history, prelock, ceiling, exclude, overlap, reviewed_points = manual
    matched_notes = match_public(pool, notes)
    if prelock is not None:
        matched_notes += prelock.to_dict('records')
    historical = historical_context(pool, history, rotations, slate)
    matched_points = match_public(pool, projections)
    if reviewed_points is not None:
        if not reviewed_points.fanduel_id.isin(pool.fanduel_id).all():
            st.error('LineupExperts points must use player IDs from the loaded contest.')
            return
        matched_points += reviewed_points.assign(source=LINEUPEXPERTS_TODAY).to_dict('records')
    now = datetime.now(ET)
    scored, audit = score_slate(pool, historical, matched_notes, matched_points, now,
                              manual_minutes=minutes, manual_history=minutes_history)
    missing = int((scored.eligible & ~scored.adjusted_fd_points.gt(0)).sum())
    starters = int(scored.prelock_starter.eq('starter').sum())
    if ceiling is not None:
        numeric = pd.to_numeric(ceiling.ceiling_fd_points, errors='coerce')
        if ceiling.fanduel_id.duplicated().any() or not ceiling.fanduel_id.isin(scored.fanduel_id).all():
            st.error('Ceilings must contain unique player IDs from this FanDuel contest.')
        else:
            scored['ceiling_fd_points'] = scored.fanduel_id.map(dict(zip(ceiling.fanduel_id, numeric)))
    from nba_checkpoint_changes import compare_checkpoints
    checkpoint_key = (*research_scope, sha256(daily_bytes).hexdigest())
    previous_checkpoint = st.session_state.get('slate_reviewed_checkpoint')
    if previous_checkpoint is not None and previous_checkpoint[0] == checkpoint_key:
        try:
            changes = compare_checkpoints(previous_checkpoint[1], scored)
        except ValueError as exc:
            st.info(f'Checkpoint comparison unavailable: {exc}')
        else:
            if not changes.empty:
                st.warning(f'{len(changes)} players have changed eligibility, roles, confidence or projected values. Reassess candidates before lock.')
                with st.expander('Changes since previous reviewed pool', expanded=True):
                    st.dataframe(changes.drop(columns='fanduel_id').round(3), hide_index=True)
            elif refresh:
                st.caption('No player-level decision changes detected in this refresh. Source freshness and coverage still require review.')
    st.session_state['slate_reviewed_checkpoint'] = (checkpoint_key, scored.copy(deep=True))
    if missing:
        st.warning(f'{missing} eligible players lack usable projections. Results are provisional until those players are reviewed.')
    st.caption(f'{len(historical)} players with recent minutes evidence · {starters} official starters matched')
    usable = scored.loc[scored.eligible & scored.adjusted_fd_points.gt(0)]
    blends = int(usable.blend_status.eq('60/40 blend applied').sum())
    independent_count = int(usable.projection_source_count.ge(2).sum())
    st.caption(f'Independent point coverage (2+ fresh sources): {independent_count}/{len(usable)} usable players · 60/40 blend applied: {blends}/{len(usable)}')
    if not blends:
        st.warning('No verified 60/40 blends applied. Scores use DAILY and applicable reviewed minutes/status adjustments; independent scoring coverage is incomplete.')
    if slate < now.date():
        st.info('Historical slate: this session does not reconstruct the original pre-lock research. Use frozen archived projections for a true historical replay.')
    with st.expander('Exact contest coverage by research provider'):
        from slate_research import public_coverage
        coverage_table = public_coverage(scored, notes, projections)
        st.caption('Returned rows can include other contests or unmatched names. Matched eligible players are unique contest IDs, before freshness, disagreement and scoring checks. Zero coverage is not evidence that a player is unavailable.')
        st.dataframe(coverage_table, hide_index=True)
        st.download_button('Download source coverage', coverage_table.to_csv(index=False),
                           file_name=f'{slate}-{contest_id}-source-coverage.csv', mime='text/csv')
    with st.expander('Scoring coverage and blend exclusions'):
        st.dataframe(scored.groupby('blend_status', dropna=False).size().rename('Players').reset_index(), hide_index=True)
        st.caption('Two fresh agreeing independent point sources are required for a blend. Reviewed minutes/status adjustments take priority; a missing blend is not automatically a reason to change weights.')

    from nba_research_triage import attach_rate_context, disagreement_queue, team_opportunity_review, paired_source_coverage
    queue = disagreement_queue(scored)
    paired_players, paired_providers = paired_source_coverage(scored, now)
    with st.expander('Independent production-rate source coverage'):
        two_pairs = int(paired_players['Paired providers'].ge(2).sum())
        st.caption(f'{two_pairs}/{len(paired_players)} eligible players have two or more fresh same-provider points/minutes pairs. This is an upper bound; injury timing and rate agreement still require review.')
        st.dataframe(paired_providers, hide_index=True)
        if two_pairs < len(paired_players):
            st.dataframe(paired_players.loc[paired_players['Paired providers'].lt(2)].merge(scored[['fanduel_id','fanduel_name','team']], on='fanduel_id', validate='one_to_one').drop(columns='fanduel_id'), hide_index=True)
    from nba_matchup_context import matchup_context
    from nba_shadow_research import freeze_research_features
    with st.expander('Historical research window'):
        st.caption('The longer window feeds both discrepancy review and frozen experimental evidence. Reviewed live scoring continues to use its established recent rotation inputs.')
        longer = st.checkbox('Load a longer rotation window', key=f'rotation_window_{contest_id}_{slate}')
    rotation_rows, coverage = rotations, rotation_status
    if longer:
        with st.spinner('Checking up to ten recent team games…'):
            rotation_rows, coverage = extended_rotations(slate, tuple(sorted(set(pool.game))))
    recent_rates, recent_absences = opportunity_evidence(scored, rotation_rows, slate)
    team_review = team_opportunity_review(scored, audit, now)
    if not team_review.empty:
        st.warning(f'{len(team_review)} eligible players on teams with reviewed OUT or role-change confirmations. Recheck teammate opportunities before lock.')
        with st.expander('Team opportunity refresh review', expanded=True):
            st.caption('Source timestamps after confirmation do not prove that the provider incorporated the news. These are research checks only; no automatic point or minutes changes.')
            st.dataframe(team_review.drop(columns='fanduel_id'), hide_index=True)
            st.download_button('Download team opportunity review', team_review.to_csv(index=False),
                               file_name=f'{slate}-team-opportunity-review.csv', mime='text/csv')
    matchup = matchup_context(scored, rotation_rows, slate)
    if not queue.empty:
        queue = attach_rate_context(queue, recent_rates)
        if not matchup.empty:
            queue = queue.merge(matchup, on='fanduel_id', how='left', validate='one_to_one')
    with st.expander(f'Full-pool disagreement review ({len(queue)} eligible players)'):
        st.caption('Research priority only: large point/minute discrepancies and missing projections are surfaced without changing scores. Agreement against DAILY is distinct from conflict between independent providers. Time and rate effects use only same-provider paired points/minutes, and may cover fewer sources than the overall point consensus. Historical production is minutes-weighted over complete recent official box scores; sample size is shown. This is descriptive evidence, not a matchup or usage-adjusted forecast.')
        if queue.empty:
            st.info('No flagged discrepancies in available evidence; this does not certify complete source coverage.')
        else:
            st.dataframe(queue.drop(columns='research_priority'), hide_index=True)
            st.download_button('Download disagreement review CSV', queue.to_csv(index=False),
                               file_name=f'{slate}-research-disagreements.csv', mime='text/csv')
            if not matchup.empty:
                st.caption('Pace uses estimated possessions from complete final team box scores, normalized to 48 minutes. Defensive rating is opponent points per 100 estimated possessions; recent team samples are descriptive, not matchup-adjusted player projections.')
            if not recent_rates.empty:
                role_fields = ['fanduel_id', 'Player', 'Minutes as starter', 'Minutes off bench',
                               'FD/min as starter', 'FD/min off bench', 'Starter complete FD games',
                               'Bench complete FD games', 'Starter complete FD minutes',
                               'Bench complete FD minutes', 'Starter/bench FD rate evidence',
                               'Opportunities/min as starter', 'Opportunities/min off bench',
                               'Starter/bench opportunity evidence']
                role_review = recent_rates.loc[recent_rates.fanduel_id.isin(queue.fanduel_id), role_fields]
                if not role_review.empty:
                    st.caption('Observed starter and bench splits for flagged players. Neither role is inferred from missing starter status.')
                    st.dataframe(role_review.drop(columns='fanduel_id'), hide_index=True)
            if not recent_absences.empty:
                absence_review = recent_absences.loc[recent_absences.fanduel_id.isin(queue.fanduel_id)]
                if not absence_review.empty:
                    st.caption('Observed splits for flagged players with currently OUT teammates. Comparisons are not causal; overlapping absences must not be added together.')
                    st.dataframe(absence_review.drop(columns=['fanduel_id', 'Box-score sources']), hide_index=True)
                    st.download_button('Download flagged-player absence evidence', absence_review.to_csv(index=False),
                                       file_name=f'{slate}-disagreement-absence-evidence.csv', mime='text/csv')


    archived_ownership = None
    archived_matchwiz = None
    archived_market_events = ()
    reference_status = {}
    if slate == now.date():
        with st.expander('Check all public projection reference boards'):
            from slate_research import get_reference_research
            st.caption('One refresh checks LineupExperts, FantasySportsEdge, Fantasy Team Advisors, MatchWiz and KeelStats together. Reference estimates are not extra independent scoring votes.')
            reference_key = ('slate_reference_boards', str(contest_id), str(slate), checked_at.isoformat(),
                             tuple(sorted(set(pool.game))))
            reference_retry = st.button('Recheck reference boards only', key='slate_all_references')
            saved_reference = st.session_state.get('slate_reference_snapshot')
            if refresh or reference_retry or saved_reference is None or saved_reference[0] != reference_key:
                with st.spinner('Checking public reference boards…'):
                    st.session_state['slate_reference_snapshot'] = (
                        reference_key, get_reference_research(slate, datetime.now(ET), tuple(sorted(set(pool.game)))))
            now = datetime.now(ET)
            saved_reference = st.session_state.get('slate_reference_snapshot')
            if saved_reference is not None and saved_reference[0] == reference_key:
                reference_boards, reference_status = saved_reference[1]
                reference_status = dict(reference_status)
                for name, result in reference_boards.items():
                    rows, stamp = result[:2]
                    if name == 'LineupExperts':
                        reference = pd.DataFrame(match_public(scored, rows))
                        if not reference.empty:
                            reference = reference.drop_duplicates('fanduel_id', keep=False)
                            compared = scored.loc[scored.eligible, ['fanduel_id','fanduel_name','projected_fd_points','adjusted_fd_points']].merge(
                                reference[['fanduel_id','reference_fd']], on='fanduel_id', validate='one_to_one')
                            compared['Reference minus model'] = (compared.reference_fd - compared.adjusted_fd_points).round(2)
                            st.dataframe(compared.drop(columns='fanduel_id'), hide_index=True)
                            matched_count = len(compared)
                        else:
                            matched_count = 0
                        reference_status[name] += f'; {matched_count} eligible matches; publication time unverified'
                    elif name in ('MatchWiz', 'KeelStats'):
                        from slate_research import compare_keelstats
                        compared = compare_keelstats(scored, rows)
                        if name == 'MatchWiz':
                            archived_matchwiz = rows
                            caveat = 'Publication time unverified; partial stats and projected roles only.'
                        else:
                            caveat = 'Returning-player impact omitted from redistribution; historical L10 and starts are not projections.'
                        st.caption(f'{name}: {caveat}')
                        reference_status[name] += f'; {len(compared)} eligible matches'
                        if name == 'MatchWiz':
                            reference_status[name] += '; publication time unverified'
                        if not compared.empty:
                            st.dataframe(compared.drop(columns='fanduel_id'), hide_index=True)
                            st.download_button(f'Download {name} comparison', compared.to_csv(index=False),
                                               file_name=f'{slate}-{contest_id}-{name.lower()}.csv', mime='text/csv',
                                               key=f'all_refs_{name}_download')
                    else:
                        matched = render_reference_board(scored, rows, stamp, name,
                                                         'Reference only; independent provenance not verified.', key_prefix='all_refs_')
                        reference_status[name] += f'; {len(matched)} eligible matches'
                for name, status in reference_status.items():
                    st.write(f'**{name}** · {status}')
                from slate_research import reference_review_queue
                reference_queue = reference_review_queue(scored, reference_boards, now)
                st.caption('Research priorities: missing projections first, then large points or minutes discrepancies. Provider rows are not independent votes; undated estimates require verification.')
                if reference_queue.empty:
                    st.info('No actionable reference discrepancies found in the available boards. This does not establish complete coverage.')
                else:
                    st.write(f'{reference_queue.fanduel_id.nunique()} eligible players flagged for further research.')
                    st.dataframe(reference_queue.drop(columns='fanduel_id'), hide_index=True)
                    st.download_button('Download reference research priorities', reference_queue.to_csv(index=False),
                                       file_name=f'{slate}-{contest_id}-reference-review.csv', mime='text/csv',
                                       key='slate_reference_review_download')
    with st.expander('Complete saved NBA research checklist'):
        from research_source_registry import research_checklist
        checklist = research_checklist('NBA', [*source_status, *reference_status.items()])
        st.caption('This is the full saved research stack, not just accepted numerical estimates. A reference or manual source is not marked verified merely because it is listed.')
        st.dataframe(checklist, hide_index=True)
    with st.expander('Sources and checks'):
        st.caption(f'Research checked {checked_at:%b %d, %I:%M %p ET}. Statuses and starters only count when sourced.')
        for name, status in source_status:
            st.write(f'**{name}** · {status}')
        st.caption('With two agreeing independent sources, the projection uses 60% DAILY and 40% independent estimates weighted by recency. Confirmed status and verified minutes adjustments take priority.')
        if extra:
            st.write(f'{extra} DAILY rows are outside the exact match to this contest or need identity review.')
        st.markdown('**Reviewed research references** · '
                    '[LineupExperts](https://www.lineupexperts.com/basketball/projections?flt_pos=Utility&flt_proj_time_period=Today) · '
                    '[NBA House](https://nbahouse.net/lab) · '
                    '[WalterPicks](https://www.walterpicks.com/)')
        if slate == now.date() and st.button('Compare with free LineupExperts projections'):
            try:
                reference = pd.DataFrame(match_public(pool, public_lineupexperts_reference(slate, now.date())))
                if reference.empty:
                    st.info('No unambiguous team and matchup matches in the current LineupExperts view.')
                else:
                    reference = reference.drop_duplicates('fanduel_id', keep=False)
                    compared = scored[['fanduel_id', 'fanduel_name', 'projected_fd_points']].merge(
                        reference[['fanduel_id', 'reference_fd']], on='fanduel_id', validate='one_to_one')
                    compared['Difference'] = (compared.reference_fd - compared.projected_fd_points).round(2)
                    st.caption('FanDuel points calculated from public projected stats. The source does not publish a verified update time. Reference only.')
                    st.dataframe(compared.drop(columns='fanduel_id').rename(columns={
                        'fanduel_name': 'Player', 'projected_fd_points': 'DAILY FD', 'reference_fd': 'LineupExperts FD',
                    }), hide_index=True)
            except (OSError, ValueError, KeyError, TypeError):
                st.info('The free LineupExperts comparison is currently unavailable.')
        st.caption('Use optional reviewed inputs for LineupExperts, FantasyProjections, Linemate and WalterPicks when a dated feed is unavailable.')
        st.markdown('[DraftEdge NBA projection board](https://draftedge.com/nba/nba-daily-projections/)')
        if slate == now.date():
            st.markdown(f'[Fantasy Team Advisors FanDuel board]({FTA_NBA_BOARD})')
            if st.button('Check FantasySportsEdge'):
                try:
                    rows, stamp = fantasysportsedge_reference(slate, now)
                    render_reference_board(scored, rows, stamp, 'FantasySportsEdge',
                                           'FanDuel main-slate estimates. Upstream source overlap is unverified.')
                except (OSError, TypeError, ValueError, KeyError):
                    st.info('FantasySportsEdge comparison is unavailable for this slate.')
            if st.checkbox('Include Fantasy Team Advisors estimates in the slate save', key=f'fta_{slate}_{contest_id}'):
                try:
                    rows, stamp, label, total = public_fta_reference(slate, checked_at, tuple(sorted(set(pool.game))))
                    matched = render_reference_board(scored, rows, stamp, 'Fantasy Team Advisors',
                                                     f'{label} public preview covers {len(rows)} of {total} source players. Ownership and ceilings are provider estimates.')
                    if not matched.empty and matched.reference_ownership.notna().any():
                        archived_ownership = (matched, stamp, FTA_NBA_BOARD, label)
                except (OSError, TypeError, ValueError, KeyError):
                    st.info('No current Fantasy Team Advisors FanDuel preview matched every game in this contest.')
        market_file = st.file_uploader('Optional NBA market snapshot (Odds API JSON)', type='json', key='nba_market')
        if market_file is not None:
            try:
                if market_file.size > 1024 * 1024:
                    raise ValueError('Market snapshot exceeds 1 MiB.')
                events = json.loads(market_file.getvalue())
                if isinstance(events, dict):
                    events = events.get('data', [events])
                    if isinstance(events, dict):
                        events = [events]
                if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
                    raise ValueError('Expected a list of market events.')
                market = game_market_evidence(events, slate, now, set(pool.game))
                player_markets = player_market_evidence(events, slate, now, pool)
            except (ValueError, TypeError, KeyError, AttributeError):
                st.warning('Use a valid Odds API snapshot with decimal odds.')
            else:
                if market.empty:
                    st.info('No fresh, pre-tip totals and spreads matched the contest games.')
                else:
                    st.caption('Market-implied team totals are research estimates. Fair over probability uses matched decimal prices at the displayed total. Markets are shown for comparison.')
                    st.dataframe(market, hide_index=True)
                if not player_markets.empty:
                    archived_market_events = events
                    st.caption('Compare each DAILY stat forecast with its sportsbook threshold. A positive gap means '
                               'DAILY is above the line. Market thresholds and fair over probabilities are research '
                               'references. Gaps are blank when DAILY has no matching stat.')
                    st.dataframe(player_markets.drop(columns='fanduel_id'), hide_index=True)
                    st.download_button('Download matched player props', player_markets.to_csv(index=False),
                                       'nba_player_props.csv', mime='text/csv')
        if len(audit):
            st.dataframe(audit[['fanduel_id', 'source', 'observed_at', 'status', 'starter', 'role', 'review']],
                         hide_index=True)
    with st.expander('Rotation and injury opportunity evidence'):
        rotation_summary, absence_splits = recent_rates, recent_absences
        st.caption(coverage)
        if rotation_summary.empty:
            st.info('No verified prior box scores matched this player pool.')
        else:
            st.dataframe(rotation_summary.drop(columns=['fanduel_id', 'Box-score sources']), hide_index=True)
        if not absence_splits.empty:
            st.caption('These comparisons use explicit box-score absences for teammates currently ruled out. Small samples are shrunk toward zero. The estimates do not change projections.')
            st.dataframe(absence_splits.drop(columns=['fanduel_id', 'Box-score sources']), hide_index=True)
            st.download_button('Download rotation evidence', absence_splits.to_csv(index=False),
                               'rotation_absences.csv', mime='text/csv')
    issue_count = int(scored.import_issue.ne('').sum())
    with st.expander(f'Full player pool · {len(scored)} players · {issue_count} import flags'):
        display = scored[['fanduel_name', 'adjusted_fd_points', 'research_attention', 'team', 'salary',
                          'roster_eligibility', 'injury_flag',
                          'prelock_status', 'prelock_starter', 'prelock_role', 'projected_minutes', 'recent_mpg', 'independent_minutes',
                          'adjusted_minutes', 'projected_fd_points', 'independent_fd_points',
                          'blended_fd_points', 'projection_source_estimates', 'projection_source_count', 'projection_method', 'blend_status',
                          'minutes_method', 'import_issue', 'identity_match']]
        st.dataframe(display.rename(columns={
            'fanduel_name':'Player', 'projected_fd_points':'DAILY FD', 'adjusted_fd_points':'Adjusted FD',
            'independent_fd_points':'Independent FD', 'blended_fd_points':'Weighted blend FD', 'recent_mpg':'Recent minutes',
            'prelock_status':'Official status', 'prelock_starter':'Starter',
        }), hide_index=True)
        st.download_button('Download reviewed pool', scored.to_csv(index=False), 'reviewed_pool.csv', mime='text/csv')

    st.header('3. Challenge and optimize')
    objective = 'adjusted_fd_points'
    if 'ceiling_fd_points' in scored:
        covered = scored.eligible & scored.adjusted_fd_points.gt(0)
        if exclude:
            covered &= ~scored.confidence.isin(['low', 'missing'])
        ceilings = scored.loc[covered, 'ceiling_fd_points']
        if covered.any() and (ceilings.ge(scored.loc[covered, 'adjusted_fd_points']) & ceilings.lt(float('inf'))).all():
            if st.checkbox('Prioritize researched GPP upside', value=True, key='slate_gpp'):
                scored['gpp_objective'] = .75 * scored.adjusted_fd_points + .25 * scored.ceiling_fd_points
                objective = 'gpp_objective'
        else:
            st.warning('Ceilings must cover the usable pool and be at least the adjusted projection for each player.')
    if objective == 'adjusted_fd_points':
        st.caption('Ranks by adjusted FanDuel points. Review ceiling, correlation and ownership as GPP inputs become available.')
    else:
        st.caption('Ranks by 75% adjusted points and 25% reviewed ceiling. This score does not estimate ownership or correlation.')
    # Research can take time: calculate lock state from a fresh clock.
    now = datetime.now(ET)
    started = set()
    research_replay = slate < now.date()
    schedule = []
    complete = False
    if slate == now.date():
        schedule = public_slate_schedule(slate)
        started, complete = started_contest_games(schedule, pool.game, now)
        if started:
            st.warning(f'{len(started)} contest games have reached tip. Fresh lineup generation is closed.')
            if not complete:
                st.info('Late swap requires verified NBA tip times for every contest game.')
        elif not complete:
            st.info('NBA tip times could not be verified for every contest game. Confirm the contest lock in FanDuel.')
    if research_replay:
        st.caption('Historical replay. Generated lineups are for research.')
    if not started:
        render_challenger(scored, exclude_uncertain=exclude)
    signature = sha256(f'{slate}:{overlap}:{exclude}:{objective}:'.encode() + scored.to_csv(index=False).encode()).hexdigest()
    prepared_key = (str(contest_id), str(slate), sha256(contest_bytes).hexdigest())
    from nba_checkpoint_changes import candidate_fingerprint, can_reuse_candidates
    try:
        candidate_key = candidate_fingerprint(scored, (*prepared_key, sha256(daily_bytes).hexdigest()),
                                              overlap, exclude, objective)
    except ValueError:
        candidate_key = signature
    if started and complete and len(started) < pool.game.map(matchup_key).nunique():
        with st.expander('Find a late swap'):
            locked_ids = set(scored.loc[scored.game.map(matchup_key).isin(started), 'fanduel_id'])
            st.caption('Match the players and slots in your FanDuel entry. Verify locks in FanDuel before applying a swap.')
            method = st.radio('How to enter your lineup', ['Select players', 'Upload CSV'], key='slate_swap_entry_method')
            roster = None
            if method == 'Upload CSV':
                st.caption('Include slot and fanduel_id columns. Keep the two UTIL rows in entry order.')
                entered = st.file_uploader('Entered lineup CSV', type='csv', key='slate_late_swap')
                try:
                    roster = read_optional(entered, {'slot', 'fanduel_id'}, id_column='fanduel_id')
                except ValueError as exc:
                    st.error(str(exc))
            else:
                sorted_pool = scored.sort_values(['fanduel_name', 'fanduel_id'], kind='stable')
                labels = {row.fanduel_id: f'{row.fanduel_name} · {row.team} · ${int(row.salary):,} · {row.fanduel_id}'
                          + (' · Locked' if row.fanduel_id in locked_ids else '')
                          for row in sorted_pool.itertuples()}
                eligibility = sorted_pool.roster_eligibility.map(allowed_slots)
                choices = []
                for index, slot in enumerate(SLOTS):
                    label = f'UTIL {index - 6}' if slot == 'UTIL' else slot
                    players = sorted_pool.loc[eligibility.map(lambda positions: slot in positions), 'fanduel_id']
                    choices.append(st.selectbox(label, players.tolist(), index=None, format_func=labels.__getitem__,
                                                key=f'slate_swap_{contest_id}_{slate}_{index}'))
                if all(choices):
                    roster = pd.DataFrame({'slot': SLOTS, 'fanduel_id': choices})
            if roster is not None:
                roster_hash = sha256(roster[['slot', 'fanduel_id']].to_csv(index=False).encode()).hexdigest()
                swap_key = (signature, roster_hash, tuple(sorted(started)))
                if st.button('Find strongest legal lineup', key='slate_late_swap_run'):
                    st.session_state.pop('late_swap_result', None)
                    try:
                        current = datetime.now(ET)
                        current_started, current_complete = started_contest_games(
                            schedule, pool.game, current)
                        if not current_complete or current_started != started:
                            raise ValueError('Game locks changed; refresh before solving.')
                        open_games = set(pool.game.map(matchup_key)) - current_started
                        next_tips = []
                        for entry in schedule:
                            away, home = (team_code((entry.get(side) or {}).get('teamTricode', ''))
                                          for side in ('awayTeam', 'homeTeam'))
                            if matchup_key(f'{away}@{home}') not in open_games:
                                continue
                            tip = pd.to_datetime(entry.get('gameTimeUtc'), utc=True, errors='coerce')
                            if pd.notna(tip) and tip.tz_convert(ET).date() == current.date():
                                next_tips.append(tip)
                        if not next_tips:
                            raise ValueError('Cannot verify the next open game tip.')
                        budget = min(35.0, (min(next_tips)-current).total_seconds()-30)
                        if budget <= 0:
                            raise ValueError('Too close to the next game lock for a new late-swap solve.')
                        swap = optimize_late_swap(scored, roster, locked_ids, exclude_uncertain=exclude,
                                                  time_budget_seconds=budget)
                        fresh_started, fresh_complete = started_contest_games(
                            public_slate_schedule(slate), pool.game, datetime.now(ET))
                        if not fresh_complete or fresh_started != started:
                            raise ValueError('Game locks changed during optimization; refresh before applying any swaps.')
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state['late_swap_result'] = (swap_key, swap)
                saved_swap = st.session_state.get('late_swap_result')
                if saved_swap is not None and saved_swap[0] == swap_key:
                    swap = saved_swap[1]
                    if not swap.solver_optimal.all():
                        st.warning('The solver found a legal candidate. Its optimality is unverified.')
                    from nba_swap_execution import find_executable_layout, LABELS
                    try:
                        layout, steps = find_executable_layout(
                            scored, swap.entered_fanduel_id.tolist(), swap.fanduel_id.tolist(), locked_ids)
                    except ValueError as exc:
                        st.error(f'Candidate is not executable: {exc}. Keep your current entry.')
                        layout, steps = None, None
                    checked_started, checked_complete = started_contest_games(
                        public_slate_schedule(slate), pool.game, datetime.now(ET))
                    if not checked_complete or checked_started != started:
                        st.session_state.pop('late_swap_result', None)
                        steps = None
                        st.warning('Game locks changed during validation; refresh and recheck before editing.')
                    if steps is None:
                        st.warning('No verified direct replacement sequence found within the search limit. Keep your current entry.')
                    else:
                        if not steps:
                            st.info('Keep the current lineup; no replacements required.')
                        lookup = scored.set_index('fanduel_id')
                        final = lookup.loc[list(layout), ['fanduel_name', 'team', 'salary']].reset_index()
                        final.insert(0, 'slot', list(LABELS))
                        final['entered_player'] = swap.entered_player.tolist()
                        final['locked'] = final.fanduel_id.isin(locked_ids)
                        st.caption(f'{int(final.locked.sum())} locked · {len(steps)} ordered replacements · '
                                   f'${int(swap.entered_salary.sum()):,} before · ${int(final.salary.sum()):,} after')
                        if swap.fd_points_delta.notna().all():
                            st.caption(f'Projected points change {swap.fd_points_delta.sum():+.2f}')
                        st.dataframe(final, hide_index=True)
                        if steps:
                            st.caption('Apply these replacements in order. Recheck every game lock and player status in FanDuel first.')
                            st.dataframe(pd.DataFrame(steps), hide_index=True)
                            st.download_button('Download ordered swap instructions', pd.DataFrame(steps).to_csv(index=False),
                                               'late_swap_steps.csv', key='slate_swap_steps_download')
                            st.download_button('Download late-swap candidate', final.to_csv(index=False),
                                               'late_swap_candidate.csv', key='slate_late_swap_download')
    key = 'slate_results'
    active_before = st.session_state.get(key)
    if active_before is not None:
        same_inputs = active_before[0] == candidate_key
        same_evidence = len(active_before) == 3 and active_before[2] == signature
        if not same_inputs or (not same_evidence and not can_reuse_candidates(active_before[1])):
            st.session_state.pop(key, None)
            st.info('Candidate inputs changed or the earlier solve was incomplete. Fresh optimization is required.')
        elif not same_evidence:
            st.session_state[key] = (candidate_key, active_before[1], signature)
            st.caption('Exact candidate inputs unchanged; retained the previously proven-optimal portfolio and alternative. Review current research and locks before entry.')
    previous_portfolio = st.session_state.get('last_complete_portfolio')
    auto_reopt = (refresh and slate == datetime.now(ET).date() and complete and not started
                  and previous_portfolio is not None and previous_portfolio[0] == prepared_key
                  and key not in st.session_state)
    requested = st.button('Generate four lineups', type='primary', key='slate_optimize', disabled=bool(started))
    if requested or auto_reopt:
        try:
            with st.spinner('Optimizing and checking legal alternatives…'):
                budget = 180.0
                if slate == datetime.now(ET).date() and complete:
                    current = datetime.now(ET)
                    current_started, still_complete = started_contest_games(schedule, pool.game, current)
                    if current_started or not still_complete:
                        raise ValueError('Contest lock changed. Refresh before generating or entering a lineup.')
                    matchups = {matchup_key(game) for game in pool.game}
                    tips = [pd.to_datetime(entry.get('gameTimeUtc'), utc=True, errors='coerce')
                            for entry in schedule
                            if matchup_key('@'.join(team_code((entry.get(side) or {}).get('teamTricode', ''))
                                                      for side in ('awayTeam', 'homeTeam'))) in matchups]
                    tips = [tip for tip in tips if pd.notna(tip) and tip.tz_convert(ET).date() == current.date()]
                    if not tips:
                        raise ValueError('Cannot verify the first contest tip.')
                    budget = min(budget, (min(tips) - current).total_seconds() - 30)
                    if budget <= 0:
                        raise ValueError('Too close to contest lock for a new solve; recheck existing entries.')
                result = generate_and_challenge(scored, overlap, exclude, objective, time_budget_seconds=budget)
                if slate == datetime.now(ET).date() and complete:
                    fresh_started, fresh_complete = started_contest_games(schedule, pool.game, datetime.now(ET))
                    if fresh_started or not fresh_complete:
                        raise ValueError('Lock changed during optimization. Do not enter these pre-tip candidates.')
                if not result[0].empty:
                    st.session_state[key] = (candidate_key, result, signature)
                    if can_reuse_candidates(result):
                        # Preserve a complete proven-optimal portfolio independently of changing
                        # research inputs. Never relabel its old projections as current.
                        st.session_state['last_complete_portfolio'] = (
                            prepared_key, candidate_key, result[0].copy(deep=True))
                else:
                    st.warning('No legal candidate returned within the budget. Existing results were not replaced.')
        except ValueError as exc:
            st.error(str(exc))
    st.header('4. Review results')
    prior = st.session_state.get('last_complete_portfolio')
    if prior is not None and prior[0] == prepared_key:
        active = st.session_state.get(key)
        if (prior[1] != candidate_key or active is None
                or active[1][0].lineup.nunique() < 4):
            with st.expander('Last complete portfolio — reference only', expanded=True):
                st.warning('Earlier candidate snapshot, not a verified current entry or fresh recommendation. Do not submit these unchanged without checking current statuses, projections and locks.')
                historical = prior[2][['lineup','slot','fanduel_id','player','salary','adjusted_fd_points']].copy()
                historical = historical.rename(columns={'adjusted_fd_points':'previous_fd_points'})
                lookup = scored.set_index('fanduel_id')
                historical['current_fd_points'] = historical.fanduel_id.map(lookup.adjusted_fd_points)
                historical['current_eligible'] = historical.fanduel_id.map(lookup.eligible).fillna(False)
                historical['current_game_started'] = historical.fanduel_id.map(
                    lookup.game.map(matchup_key).isin(started)).fillna(False)
                st.dataframe(historical, hide_index=True)
                st.caption('No historical portfolio is substituted into current optimization or the reviewed-slate archive. Started-game flags depend on the schedule available to this session.')
    lineups = None
    if key in st.session_state:
        lineups, comparison, alternative = st.session_state[key][1]
        if started:
            st.caption('Saved pre-tip candidates for this session.')
        show_results(scored, lineups, comparison, alternative)
        if not lineups.empty:
            with st.expander('Experimental simulated candidate comparison'):
                st.caption('Conditional on playing, with independent player residuals. Uses reviewed adjusted minutes and FD points, not raw DAILY. No ownership, game correlation or contest win probability is inferred; optimizer rankings are unchanged.')
                import os
                from history_panel import owner_can_view_history
                from nba_archive_training import load_prior_replays, prior_contests
                owner = os.environ.get('DFS_HISTORY_OWNER_EMAIL', '').strip()
                token = (os.environ.get('DFS_HISTORY_SNAPSHOT_TOKEN') or
                         os.environ.get('DFS_HISTORY_INTAKE_TOKEN', '')).strip()
                archive_available = bool(owner and token and owner_can_view_history(owner, st.user)
                                         and prior_contests(history, slate))
                use_archive = (st.checkbox('Use earlier private slate archives automatically', value=True,
                                           key='slate_simulation_archive') if archive_available else False)
                files = [] if use_archive else st.file_uploader(
                    'Earlier verified player_replay.csv exports', type='csv',
                    accept_multiple_files=True, key='slate_simulation_history')
                if use_archive:
                    st.caption('Checks up to three earlier saved dates, one broadest contest per date, and eight versions per contest. Uses the latest valid full pre-tip capture and verified final NBA games.')
                stress = st.checkbox('Compare hypothetical game/team dependence and candidate ceilings', value=True,
                                     key='slate_simulation_stress')
                if (use_archive or files) and st.button('Simulate current candidates', key='slate_simulation_run'):
                    try:
                        from nba_simulation import simulate_reviewed_candidates
                        if use_archive:
                            with st.spinner('Verifying earlier private captures and final NBA box scores…'):
                                training, coverage = load_prior_replays(history, slate, token)
                            st.dataframe(coverage, hide_index=True)
                            if training.empty:
                                raise ValueError('No verified earlier frozen replay found. Use the CSV fallback if available.')
                        else:
                            if sum(file.size for file in files) > 8 * 1024 * 1024:
                                raise ValueError('Combined replay files must be smaller than 8 MiB.')
                            training = pd.concat([pd.read_csv(file, dtype={'fanduel_id': str})
                                                  for file in files], ignore_index=True).drop_duplicates()
                        candidates = lineups[['lineup', 'fanduel_id']].copy()
                        candidates['lineup'] = candidates.lineup.map(lambda n: f'Lineup {n}')
                        if not alternative.empty:
                            candidates = pd.concat([candidates, alternative[['fanduel_id']].assign(
                                lineup='Best distinct alternative')], ignore_index=True)
                        ranges, pairs, count, outcomes = simulate_reviewed_candidates(
                            training, scored, candidates, slate, return_draws=True)
                        st.caption(f'{count} earlier verified played training rows; 4,000 shared outcome draws.')
                        st.dataframe(ranges, hide_index=True)
                        if not pairs.empty:
                            st.dataframe(pairs, hide_index=True)
                        if stress:
                            from nba_candidate_sensitivity import candidate_sensitivity
                            ceiling, portfolio = candidate_sensitivity(outcomes, scored, candidates)
                            st.caption('Fixed hypothetical latent dependence scenarios, not measured correlations. Player distributions are preserved. Best-candidate shares compare only these supplied lineups, not the contest field; P99 is especially noisy.')
                            st.dataframe(ceiling.round(3), hide_index=True)
                            st.dataframe(portfolio.round(2), hide_index=True)
                            from nba_dependence import reviewed_dependence_evidence
                            detail, measured = reviewed_dependence_evidence(training, slate)
                            if measured.empty:
                                st.info('Insufficient earlier verified games for a held-out dependence audit. Hypothetical scenarios remain uncalibrated.')
                            else:
                                st.caption('Historical adjusted-score error cross-products, tested on later dates against a zero-dependence benchmark. These are not correlation coefficients and do not set simulation weights.')
                                st.dataframe(measured.round(3), hide_index=True)
                                st.download_button('Download held-out dependence audit', detail.to_csv(index=False),
                                                   'reviewed_dependence_audit.csv', mime='text/csv')
                            st.download_button('Download candidate sensitivity', ceiling.to_csv(index=False),
                                               'candidate_dependence_sensitivity.csv', mime='text/csv')
                    except (ValueError, KeyError, TypeError, OSError) as exc:
                        st.warning(f'Simulation unavailable: {exc}')
                elif not use_archive and not files:
                    st.info('Sign in to use eligible private archives, or supply verified earlier replay exports. Generic historical results are not substitutes for frozen DAILY points.')
        if not started and not lineups.empty:
            with st.expander('Prepare injury contingencies'):
                st.caption('Prepare before lock. These are hypothetical single-player and paired OUT portfolios, not news or late-swap instructions. Other players retain the reviewed projections.')
                contingency_key = (signature, sha256(lineups.to_csv(index=False).encode()).hexdigest())
                if st.button('Prepare scratch alternatives', key='slate_contingencies_run'):
                    try:
                        from nba_injury_contingency import prepare_contingencies
                        budget = 45.0
                        if slate == datetime.now(ET).date():
                            current = datetime.now(ET)
                            current_started, current_complete = started_contest_games(schedule, pool.game, current)
                            if current_started:
                                raise ValueError('A contest game reached tip; use lock-aware late swap instead.')
                            if current_complete:
                                matchups = {matchup_key(game) for game in pool.game}
                                tips = [pd.to_datetime(entry.get('gameTimeUtc'), utc=True, errors='coerce')
                                        for entry in schedule
                                        if matchup_key('@'.join(team_code((entry.get(side) or {}).get('teamTricode', ''))
                                                                  for side in ('awayTeam', 'homeTeam'))) in matchups]
                                tips = [tip for tip in tips if pd.notna(tip) and tip.tz_convert(ET).date() == current.date()]
                                if not tips:
                                    raise ValueError('Cannot verify contest tip times.')
                                budget = min(budget, (min(tips)-current).total_seconds()-30)
                            else:
                                budget = min(budget, 15.0)
                                st.warning('Tip times unverified. Alternatives are research only; check FanDuel.')
                        if budget <= 0:
                            raise ValueError('Too close to lock to prepare new scratch scenarios.')
                        report = prepare_contingencies(scored, lineups, time_budget_seconds=budget,
                            max_overlap=overlap, exclude_uncertain=exclude, objective_column=objective,
                            max_joint_scenarios=1)
                        if slate == datetime.now(ET).date():
                            fresh_started, _ = started_contest_games(schedule, pool.game, datetime.now(ET))
                            if fresh_started:
                                raise ValueError('Contest reached tip during the solve; do not apply these pre-tip alternatives.')
                        st.session_state['slate_contingencies_result'] = (contingency_key, report)
                        st.session_state['prepared_contingency_archive'] = (prepared_key, report)
                    except (ValueError, KeyError) as exc:
                        st.warning(str(exc))
                saved = st.session_state.get('slate_contingencies_result')
                if saved is not None and saved[0] == contingency_key:
                    report = saved[1]
                    st.caption(f"{report['completed_scenarios']}/{report['uncertain_selected_players']} selected uncertain players have complete alternative portfolios.")
                    if report['joint_scenarios_possible']:
                        st.caption(f"Paired scratch coverage: {report['joint_scenarios_completed']}/{report['joint_scenarios_requested']} requested; {report['joint_scenarios_possible']} possible pairs.")
                    if report['scenarios']:
                        st.dataframe(pd.DataFrame([{k:v for k,v in scenario.items() if k!='candidates'}
                                                    for scenario in report['scenarios']]), hide_index=True)
                        for scenario in report['scenarios']:
                            candidates = scenario['candidates']
                            if scenario['status'] == 'complete' and not candidates.empty:
                                st.download_button(f"Download {scenario['player']} OUT alternatives",
                                    candidates.to_csv(index=False), f"scratch_{scenario['out_id']}.csv",
                                    key=f"scratch_download_{scenario['out_id']}")
                    else:
                        st.info('No selected players have an unresolved probable, questionable or doubtful designation.')
        # Informational guard: this check ranks adjusted FD means, not GPP ceiling blends.
        if objective != 'adjusted_fd_points':
            st.info('Pre-lock mean-FD ranking sensitivity is not shown for the GPP ceiling-weighted objective; a GPP-objective sensitivity check is not yet validated.')
        else:
            # Informational guard: rank fragility never changes the selected optimizer lineups.
            try:
                from nba_live_prelock_fragility import rank_fragility
                fragility = rank_fragility(scored, lineups, minute_spread=2.0)
                if fragility.get('differential_players_total') is not None:
                    st.caption(
                        f"Pre-lock sensitivity coverage: {fragility['tested_differential_players']}/"
                        f"{fragility['differential_players_total']} differential players checked."
                    )
                if fragility.get('fragile'):
                    st.warning('Pre-lock ranking sensitivity: a ±2-minute player scenario changes the leading candidate. Review minutes sources before entry.')
                    with st.expander('Inspect ranking-sensitive players'):
                        st.dataframe(pd.DataFrame(fragility['rows']), hide_index=True)
                        st.caption(fragility['reason'])
                elif fragility.get('differential_players_total') is None:
                    st.info('Pre-lock ranking comparison unavailable: at least two candidate lineups are required.')
                else:
                    st.caption('Pre-lock ±2-minute differential-player check: no candidate ranking reversal detected in the tested scenarios. This does not certify projections or lock status.')
            except (ValueError, KeyError, TypeError) as exc:
                st.info(f'Pre-lock fragility audit unavailable: {exc}')

    else:
        st.caption('Generated lineups and their alternatives appear here.')
    prepared = st.session_state.get('prepared_contingency_archive')
    if prepared is not None and prepared[0] == prepared_key:
        usable = [case for case in prepared[1]['scenarios']
                  if case['status']=='complete' and not case['candidates'].empty]
        if usable:
            with st.expander('Check a prepared alternative against your current entry'):
                st.caption('Saved for this contest during this session. Refresh research first. Only complete saved scenarios are shown; current scores, status and locks are rechecked. This is a single-entry check, not portfolio optimization.')
                chosen = st.selectbox('Prepared scenario', range(len(usable)),
                                     format_func=lambda i: usable[i]['player']+' OUT',
                                     key='prepared_case_selection')
                upload = st.file_uploader('Current entered roster CSV', type='csv',
                                          key='prepared_entered_roster')
                st.caption('CSV: slot and fanduel_id, with the two UTIL rows in entry order.')
                activate = st.checkbox('Check confirmed scratch against live entry (not a hypothetical preview)',
                                       key='prepared_activate')
                if st.button('Validate prepared alternative', key='prepared_validate'):
                    try:
                        from nba_contingency_execution import plan_contingency_entry
                        entry = read_optional(upload, {'slot','fanduel_id'}, id_column='fanduel_id')
                        if entry is None:
                            raise ValueError('Supply the exact current entered roster.')
                        case = usable[chosen]
                        current = datetime.now(ET)
                        current_started, current_complete = (started_contest_games(
                            public_slate_schedule(slate), pool.game, current)
                            if slate == current.date() else (set(), False))
                        if activate and (slate != current.date() or not current_complete):
                            raise ValueError('Live validation needs verified current contest tip times.')
                        locks = set(scored.loc[scored.game.map(matchup_key).isin(current_started), 'fanduel_id'])
                        report = plan_contingency_entry(scored, entry, case['candidates'],
                            case['out_ids'], closed_players=locks, preview=not activate,
                            schedule_verified=current_complete, audit=audit, as_of=current)
                        if activate:
                            final_started, final_complete = started_contest_games(
                                public_slate_schedule(slate), pool.game, datetime.now(ET))
                            if final_started != current_started or not final_complete:
                                raise ValueError('Lock state changed during validation. Refresh and recheck.')
                        if not report['options']:
                            st.warning('No verified direct transition from this entry. Keep the entry or use a fresh lock-aware solve; check any scratch in FanDuel.')
                        else:
                            best = report['options'][0]
                            st.caption(f"{report['status']} · Candidate {best['candidate']} · Salary ${best['salary']:,}")
                            if best['current_fd_points'] is not None:
                                st.caption(f"Current projected FD: {best['current_fd_points']:.2f}")
                            if not activate:
                                st.info('Hypothetical preview only. Do not apply without current official scratch and FanDuel lock verification.')
                            else:
                                st.warning('Validated at this snapshot only. Verify FanDuel locks and all remaining availability before any edit. Recheck if news or entry changes.')
                            if best['steps']:
                                st.dataframe(pd.DataFrame(best['steps']), hide_index=True)
                            else:
                                st.info('No edits required for this candidate.')
                    except (ValueError, KeyError, TypeError) as exc:
                        st.warning(str(exc))
    if archived_ownership and lineups is not None and not lineups.empty:
        with st.expander('Candidate ownership and exposure review'):
            st.caption('Provider reference ownership, not actual contest ownership. Exposure is the share of supplied candidate lineups containing each player. Unknown estimates remain unknown; partial lineup totals are not ranked.')
            try:
                from nba_ownership import candidate_ownership_review
                ownership_pool = archive_ownership(scored, *archived_ownership)
                ownership_summary, exposure = candidate_ownership_review(
                    ownership_pool, lineups, datetime.now(ET), slate)
                st.dataframe(ownership_summary.round(2), hide_index=True)
                st.dataframe(exposure.round(2), hide_index=True)
                st.download_button('Download candidate exposure review', exposure.to_csv(index=False),
                                   'candidate_ownership_exposure.csv', mime='text/csv')
            except (ValueError, TypeError, KeyError) as exc:
                st.warning(f'Ownership comparison unavailable: {exc}')
    hashes = (sha256(contest_bytes).hexdigest(), sha256(daily_bytes).hexdigest())
    archive_pool = archive_ownership(scored, *archived_ownership) if archived_ownership else scored
    archive_pool = freeze_research_features(archive_pool, recent_rates, recent_absences, matchup)
    if archived_matchwiz is not None:
        from matchwiz_reference import freeze_matchwiz_reference
        archive_pool = freeze_matchwiz_reference(archive_pool, archived_matchwiz, slate, datetime.now(ET))
    render_slate_archive(archive_pool, slate_date=slate, generated_lineups=lineups,
                         replay_inputs=(audit, hashes), market_events=archived_market_events)


def render_site():
    st.set_page_config(page_title='DFS Model 2.0', layout='centered')
    st.title('DFS Model 2.0')
    view = st.radio('Workspace', ('Build a slate', 'Post-slate review', 'History and advanced'), horizontal=True,
                    label_visibility='collapsed', key='site_view')
    if view == 'Build a slate':
        workflow = st.container()
        history = st.container()
        with workflow:
            render_slate(history)
    elif view == 'Post-slate review':
        render_post_slate()
    else:
        render_history_panel()
        render_advanced()
