"""Shared Streamlit entry point for production and development preview."""
from datetime import date, datetime, timedelta
from functools import partial
from hashlib import sha256
import re

import pandas as pd
import streamlit as st

from advanced_ui import render_advanced
from evidence import validate_sources
from history_intake_ui import render_slate_archive
from history_panel import render_history_panel
from slate_results_ui import render_post_slate
from model import SLOTS, optimize
from prelock import REQUIRED
from slate_import import reconcile_exports
from slate_research import (
    ET, LINEUPEXPERTS_TODAY, get_public_research, historical_context, lineupexperts_reference, match_public, recent_boxscores, score_slate,
)
from slate_tools_ui import render_challenger


@st.cache_data(ttl=300, max_entries=16, show_spinner=False)
def public_research(slate, checked_at):
    # Only public data is cached across sessions. Private history is owner-gated separately.
    return get_public_research(slate, checked_at)


@st.cache_data(ttl=1800, max_entries=16, show_spinner=False)
def public_rotations(slate, games):
    return recent_boxscores(slate, set(games))


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def public_lineupexperts_reference(slate, today):
    return lineupexperts_reference(slate, today)


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
        reviewed_points = st.file_uploader('Verified LineupExperts points CSV', type='csv', key='slate_reviewed_points')
        st.caption('Optional LineupExperts data requires fanduel_id, points, and observed_at with a timezone. Use a verified source update time.')
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


def generate_and_challenge(pool, overlap, exclude, objective='adjusted_fd_points'):
    solve = partial(optimize, pool, exclude_uncertain=exclude, objective_column=objective)
    lineups = solve(number=4, max_overlap=overlap)
    if lineups.empty:
        return lineups, pd.DataFrame(), pd.DataFrame()
    # Lineup 1 has the best unconstrained objective. A single extra solve finds
    # its best distinct rival. Lineup 1 is itself a distinct rival to every other lineup.
    first = lineups[lineups.lineup.eq(1)]
    alternative = solve(number=1, exclude_rosters=(first.fanduel_id,))
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
    total = 0 if lineups.empty else lineups.lineup.nunique()
    if total < 4:
        st.warning(f'{total} legal lineups found with the current overlap setting and usable projections.')
    if not total:
        return
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
            uncertain = status.loc[roster.fanduel_id]
            review = uncertain[(uncertain.confidence.isin(['low', 'missing']))
                               | uncertain.research_attention.str.contains('Availability|disagreement|Role')]
            if len(review):
                st.caption('Review before entry: ' + ', '.join(review.fanduel_name))
    if not comparison.empty:
        with st.expander('Compare against the full pool'):
            st.caption('Each comparison uses a different legal roster from players with usable projections. Reusing the strongest rival across lineups measures the cost of portfolio overlap.')
            st.dataframe(comparison, hide_index=True)
            if not alternative.empty:
                st.download_button('Download strongest alternative to lineup 1', alternative.to_csv(index=False),
                                   'strongest_alternative.csv')
    st.download_button('Download lineups', lineups.to_csv(index=False), 'four_lineups.csv', mime='text/csv')


def render_slate(history_slot):
    st.header('1. Upload your slate')
    st.caption('FanDuel NBA classic · nine unique players · $60,000 cap')
    contest = st.file_uploader('FanDuel contest CSV', type='csv', key='slate_contest')
    daily = st.file_uploader('DAILY projection CSV', type='csv', key='slate_daily')
    now = datetime.now(ET)
    if not (contest and daily):
        with history_slot:
            render_history_panel()
        return
    try:
        pool, contest_id, extra = reconcile_exports(contest.getvalue(), daily.getvalue())
    except (ValueError, OSError, KeyError) as exc:
        st.error(str(exc))
        return
    filename_date = re.search(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)', contest.name)
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
    refresh = st.button('Refresh research', key='slate_refresh')
    # Reuse the same freshness window on reruns. A manual refresh is scoped to this session.
    window = now.replace(second=0, microsecond=0, minute=(now.minute // 5) * 5)
    refresh_key = 'slate_refreshed_at'
    if refresh:
        st.session_state[refresh_key] = now.replace(microsecond=0)
    checked_at = max(window, st.session_state.get(refresh_key, window))
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
    if missing:
        st.warning(f'{missing} eligible players lack usable projections. Results are provisional until those players are reviewed.')
    st.caption(f'{len(historical)} players with recent minutes evidence · {starters} official starters matched')
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
        if len(audit):
            st.dataframe(audit[['fanduel_id', 'source', 'observed_at', 'status', 'starter', 'role', 'review']],
                         hide_index=True)
    issue_count = int(scored.import_issue.ne('').sum())
    with st.expander(f'Full player pool · {len(scored)} players · {issue_count} import flags'):
        display = scored[['fanduel_name', 'adjusted_fd_points', 'research_attention', 'team', 'salary',
                          'roster_eligibility', 'injury_flag',
                          'prelock_status', 'prelock_starter', 'prelock_role', 'projected_minutes', 'recent_mpg', 'independent_minutes',
                          'adjusted_minutes', 'projected_fd_points', 'independent_fd_points',
                          'blended_fd_points', 'projection_source_estimates', 'projection_method',
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
    render_challenger(scored, exclude_uncertain=exclude)
    signature = sha256(f'{slate}:{overlap}:{exclude}:{objective}:'.encode() + scored.to_csv(index=False).encode()).hexdigest()
    key = 'slate_results'
    if st.button('Generate four lineups', type='primary', key='slate_optimize'):
        try:
            with st.spinner('Optimizing and checking legal alternatives…'):
                st.session_state[key] = (signature, generate_and_challenge(scored, overlap, exclude, objective))
        except ValueError as exc:
            st.error(str(exc))
    if key in st.session_state and st.session_state[key][0] != signature:
        del st.session_state[key]
        st.info('Research or slate inputs changed. Generate lineups again.')
    st.header('4. Review results')
    lineups = None
    if key in st.session_state:
        lineups, comparison, alternative = st.session_state[key][1]
        show_results(scored, lineups, comparison, alternative)
    else:
        st.caption('Generated lineups and their alternatives appear here.')
    render_slate_archive(scored, slate_date=slate, generated_lineups=lineups)


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
