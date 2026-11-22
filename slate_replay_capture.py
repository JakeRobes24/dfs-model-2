"""Attach timestamped replay evidence to the existing immutable slate packet."""
import json
from collections import defaultdict

import pandas as pd

from nba_ownership import OWNERSHIP_FIELDS
from slate_import import matchup_key, team_code


EVIDENCE_FIELDS = ('source', 'independent_group', 'observed_at', 'official',
                   'status', 'starter', 'role', 'minutes')


EVIDENCE_FIELDS_SET = set(EVIDENCE_FIELDS)


def capture_pool(pool, audit, schedule, slate, captured_at, input_hashes):
    """Record verified schedule coverage and reviewed evidence without changing scores."""
    capture = pd.Timestamp(captured_at)
    if pd.isna(capture) or capture.tzinfo is None:
        raise ValueError('Replay capture requires a timezone-aware timestamp.')
    capture = capture.tz_convert('UTC')
    candidates = defaultdict(list)
    for game in schedule:
        if not isinstance(game, dict):
            continue
        away, home = (team_code((game.get(side) or {}).get('teamTricode', ''))
                      for side in ('awayTeam', 'homeTeam'))
        stamp = pd.to_datetime(game.get('gameTimeUtc'), utc=True, errors='coerce')
        if (away and home and away != home and pd.notna(stamp)
                and stamp.tz_convert('America/New_York').date() == slate):
            started = pd.to_datetime(game.get('actualStartTimeUTC'), utc=True, errors='coerce')
            known_start = (pd.notna(started) and started <= capture
                           and started.tz_convert('America/New_York').date() == slate)
            cutoff = min(stamp, started) if known_start else stamp
            candidates[matchup_key(f'{away}@{home}')].append((stamp, cutoff))
    tips = {game: stamps[0] for game, stamps in candidates.items() if len(stamps) == 1}
    keys = pool.game.map(matchup_key)
    player_tips = pd.to_datetime(keys.map({game: stamp for game, (stamp, _) in tips.items()}), utc=True)
    cutoffs = pd.to_datetime(keys.map({game: cutoff for game, (_, cutoff) in tips.items()}), utc=True)
    known = cutoffs.notna()
    full_slate_before_tip = bool(len(pool) and known.all() and (cutoffs > capture).all())

    reviewed = {}
    if not audit.empty:
        notes = audit.loc[audit.review.eq('Reviewed') & audit.fanduel_id.isin(pool.fanduel_id)].copy()
        notes['observed_at'] = pd.to_datetime(notes.observed_at, utc=True, errors='coerce', format='mixed')
        notes = notes.loc[notes.observed_at.le(capture)].sort_values('observed_at', kind='stable')
        for player, entries in notes.groupby('fanduel_id'):
            reviewed[player] = entries[list(EVIDENCE_FIELDS)].to_json(orient='records', date_format='iso')

    archived = pool.assign(
        replay_captured_at_utc=capture.isoformat(),
        replay_scheduled_tip_utc=player_tips.map(lambda tip: tip.isoformat() if pd.notna(tip) else ''),
        replay_cutoff_utc=cutoffs.map(lambda tip: tip.isoformat() if pd.notna(tip) else ''),
        replay_schedule_source=f'https://www.nba.com/games?date={slate}',
        replay_timing='schedule_unverified',
        replay_before_full_slate_tip=full_slate_before_tip,
        replay_contest_sha256=input_hashes[0],
        replay_daily_sha256=input_hashes[1],
        replay_evidence_json=pool.fanduel_id.map(reviewed).fillna(json.dumps([])),
    )
    archived.loc[known & cutoffs.gt(capture), 'replay_timing'] = 'before_scheduled_tip'
    archived.loc[known & cutoffs.le(capture), 'replay_timing'] = 'at_or_after_cutoff'
    return archived


def build_replay_rows(pool, results, slate):
    """Export one verified full-slate capture for future walk-forward tests."""
    replay_fields = {'replay_captured_at_utc', 'replay_cutoff_utc', 'replay_scheduled_tip_utc',
                     'replay_schedule_source', 'replay_before_full_slate_tip', 'replay_timing',
                     'replay_contest_sha256', 'replay_daily_sha256', 'replay_evidence_json'}
    projection_fields = {'fanduel_id', 'fanduel_name', 'team', 'game', 'eligible', 'prelock_status',
                         'prelock_starter', 'projected_minutes', 'projected_fd_points',
                         'adjusted_minutes', 'adjusted_fd_points'}
    if pool.empty or not (replay_fields | projection_fields) <= set(pool):
        raise ValueError('This saved version predates the full pre-lock replay capture.')
    capture = pd.to_datetime(pool.replay_captured_at_utc, utc=True, errors='coerce')
    cutoffs = pd.to_datetime(pool.replay_cutoff_utc, utc=True, errors='coerce')
    tips = pd.to_datetime(pool.replay_scheduled_tip_utc, utc=True, errors='coerce')
    if (capture.nunique() != 1 or not (capture < cutoffs).all() or not (cutoffs <= tips).all()
            or not tips.dt.tz_convert('America/New_York').dt.date.eq(slate).all()
            or not pool.replay_timing.eq('before_scheduled_tip').all()
            or not pool.replay_schedule_source.eq(f'https://www.nba.com/games?date={slate}').all()
            or not pool.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()):
        raise ValueError('Replay requires a verified capture before every game in the contest.')
    for field in ('replay_contest_sha256', 'replay_daily_sha256'):
        if pool[field].nunique() != 1 or not pool[field].astype(str).str.fullmatch('[0-9a-f]{64}').all():
            raise ValueError('Could not verify both input fingerprints for this replay.')

    for encoded in pool.replay_evidence_json:
        try:
            notes = json.loads(encoded)
        except (TypeError, ValueError) as exc:
            raise ValueError('The saved replay evidence could not be read.') from exc
        if not isinstance(notes, list) or any(
                not isinstance(note, dict)
                or not EVIDENCE_FIELDS_SET <= note.keys()
                or not isinstance(note['observed_at'], str)
                or not pd.to_datetime(note['observed_at'], utc=True, errors='coerce') <= capture.iloc[0]
                for note in notes):
            raise ValueError('The saved replay evidence contains an invalid source timestamp.')

    rows = pool[sorted(projection_fields | replay_fields | (set(OWNERSHIP_FIELDS) & set(pool)))].copy()
    rows['eligible'] = rows.eligible.astype(str).str.lower().eq('true')
    rows['replay_before_full_slate_tip'] = True
    official = results[['fanduel_id', 'outcome', 'nba_actual_minutes', 'nba_fd_points', 'nba_source',
                        'recorded_fd_points']].copy()
    official['verified_outcome'] = official.outcome.map({'Played': 'played', 'Did not play': 'did_not_play'})
    official['verified_outcome'] = official.verified_outcome.where(official.nba_source.fillna('').ne(''),
                                                                   'needs_review').fillna('needs_review')
    official.loc[official.verified_outcome.eq('needs_review'), ['nba_actual_minutes', 'nba_fd_points']] = None
    rows = rows.merge(official.drop(columns='outcome'), on='fanduel_id', how='left', validate='one_to_one')
    rows['verified_outcome'] = rows.verified_outcome.fillna('needs_review')
    return rows.assign(slate_date=slate.isoformat()).rename(columns={
        'projected_minutes': 'daily_minutes', 'projected_fd_points': 'daily_points',
        'nba_actual_minutes': 'actual_minutes', 'nba_fd_points': 'actual_points',
    })
