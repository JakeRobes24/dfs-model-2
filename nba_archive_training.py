"""Read-only training data from content-addressed, pre-tip slate archives."""
from datetime import date

import pandas as pd

from history_intake import list_slate_packets, load_slate_packet
from slate_import import game_code, matchup_key
from slate_replay_capture import build_replay_rows
from slate_results import SOURCE_ERRORS, collect_final_boxes, compare_results


def prior_contests(history, target_day, *, limit=3):
    """Pick at most one contest per prior date; prefer the broadest saved pool."""
    if history is None or not {'slate_date', 'fanduel_id'} <= set(history):
        return []
    rows = history[['slate_date', 'fanduel_id']].drop_duplicates().copy()
    rows['day'] = pd.to_datetime(rows.slate_date, errors='coerce').dt.date
    rows['contest'] = rows.fanduel_id.astype(str).str.extract(r'^([0-9]{1,12})-\d+$', expand=False)
    rows = rows.loc[rows.day.notna() & rows.contest.notna()]
    rows = rows.loc[rows.day.lt(target_day)]
    counts = rows.groupby(['day', 'contest']).fanduel_id.nunique().reset_index(name='players')
    counts = counts.sort_values(['day', 'players', 'contest'], ascending=[False, False, True])
    return list(counts.drop_duplicates('day').head(limit)[['day', 'contest']].itertuples(index=False, name=None))


def load_prior_replays(history, target_day, token, *, limit=3, version_limit=8,
                       list_packets=list_slate_packets, load_packet=load_slate_packet,
                       final_boxes=collect_final_boxes):
    """Use latest chronologically valid full pre-tip capture for each earlier date.

    Every packet is checksum-verified by the archive loader, and outcomes come
    from official final boxes, never from generic or manually recorded actuals.
    A bounded scan fails closed if a contest has too many versions to compare.
    """
    if not token or type(target_day) is not date or not 1 <= limit <= 5 or not 1 <= version_limit <= 12:
        raise ValueError('A verified archive connection and bounded prior-slate scan are required.')
    replays, report = [], []
    for day, contest in prior_contests(history, target_day, limit=limit):
        row = {'date': day.isoformat(), 'contest': contest, 'played_rows': 0, 'version': ''}
        try:
            commit, folder, versions = list_packets(token, day, contest)
            if not versions or len(versions) > version_limit:
                raise ValueError('No saved versions or version scan limit exceeded.')
            valid = []
            for version in versions:
                try:
                    pool, _ = load_packet(token, commit, folder, version)
                    # Validate the full frozen capture before fetching actuals.
                    empty = pd.DataFrame(columns=['fanduel_id', 'outcome', 'nba_actual_minutes',
                                                  'nba_fd_points', 'nba_source', 'recorded_fd_points'])
                    build_replay_rows(pool, empty, day)
                    games = {matchup_key(game_code(game)) for game in pool.game}
                    if not games or '' in games:
                        continue
                    captured = pd.to_datetime(pool.replay_captured_at_utc.iloc[0], utc=True)
                    valid.append((captured, version, pool, games))
                except SOURCE_ERRORS:
                    continue
            if not valid:
                raise ValueError('No verified full pre-tip capture.')
            newest = max(item[0] for item in valid)
            latest = [item for item in valid if item[0] == newest]
            # Exact duplicate research saves are harmless; conflicting snapshots
            # at the same time must not be selected based on a hash or outcome.
            if any(not latest[0][2].equals(item[2]) for item in latest[1:]):
                raise ValueError('Conflicting captures at the latest timestamp.')
            _, version, pool, games = latest[0]
            boxes = final_boxes(day, games)
            results, finals = compare_results(pool, day, boxes, {})
            if finals != games:
                raise ValueError('Not every contest game has a verified final box score.')
            replay = build_replay_rows(pool, results, day)
            row.update(version=version[:12], played_rows=int(replay.verified_outcome.eq('played').sum()),
                       status='Verified frozen capture and final games')
            replays.append(replay)
        except SOURCE_ERRORS as exc:
            row['status'] = 'Unavailable or unverified archive/final results'
        report.append(row)
    return (pd.concat(replays, ignore_index=True) if replays else pd.DataFrame(),
            pd.DataFrame(report, columns=['date', 'contest', 'version', 'played_rows', 'status']))
