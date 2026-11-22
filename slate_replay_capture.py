"""Attach timestamped replay evidence to the existing immutable slate packet."""
import json
from collections import defaultdict

import pandas as pd

from slate_import import matchup_key, team_code


EVIDENCE_FIELDS = ('source', 'independent_group', 'observed_at', 'official',
                   'status', 'starter', 'role', 'minutes')


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

    reviewed = defaultdict(list)
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
