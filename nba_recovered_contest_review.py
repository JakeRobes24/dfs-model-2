"""Read-only outcome review of a recovered NBA contest export with file digests."""
import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from history_intake import MAX_PACKET
from model import SLOTS, allowed_slots
from nba_classic_rules import validate_team_roster
from slate_import import game_code, matchup_key, reconcile_exports
from slate_results import collect_final_boxes, compare_results, lineup_review


def load_recovered_contest(source):
    """Restore original bytes without extracting it or asserting pre-tip timing."""
    with ZipFile(source) as archive:
        entries = archive.infolist()
        if (len(entries) != 5 or len({p.filename for p in entries}) != 5
                or any(p.file_size > MAX_PACKET for p in entries)):
            raise ValueError('Expected one manifest and four bounded contest files.')
        manifest = json.loads(archive.read('manifest.json'))
        if set(manifest['files']) != set(archive.namelist()) - {'manifest.json'}:
            raise ValueError('Recovery manifest and members do not agree.')
        inputs = {}
        for name, metadata in manifest['files'].items():
            raw = archive.read(name)
            if len(raw) != metadata['bytes'] or sha256(raw).hexdigest() != metadata['sha256']:
                raise ValueError(f'Recovered bytes failed the checksum for {name}.')
            inputs[name] = raw
    expected = ('FanDuel', 'DAILY', 'reviewed_pool', 'four_lineups')
    scoped = [[raw for name, raw in inputs.items() if name.startswith(prefix)] for prefix in expected]
    if any(len(records) != 1 for records in scoped):
        raise ValueError('Recovery requires the contest, DAILY, reviewed pool and lineup exports.')
    contest, daily, pool_csv, lineup_csv = [records[0] for records in scoped]
    pool, _, _ = reconcile_exports(contest, daily)
    reviewed = pd.read_csv(BytesIO(pool_csv), dtype={'fanduel_id': str})
    lineups = pd.read_csv(BytesIO(lineup_csv), dtype={'fanduel_id': str})
    return manifest, pool, reviewed, lineups


def verify_recovered_lineups(contest, reviewed, lineups, *, contest_id):
    """Use contest authority for salary, team and both UTIL slots."""
    if (not reviewed.fanduel_id.is_unique or set(contest.fanduel_id) != set(reviewed.fanduel_id)
            or not contest.fanduel_id.str.split('-').str[0].eq(contest_id).all()):
        raise ValueError('Reviewed and original pools must match the exact contest.')
    if lineups.empty or lineups.lineup.isna().any():
        raise ValueError('Recovered candidates require lineup identities.')
    pool = contest.set_index('fanduel_id')
    prior = reviewed.set_index('fanduel_id')
    metadata = ['team', 'game', 'salary', 'roster_eligibility']
    if not pool[metadata].equals(prior.loc[pool.index, metadata]):
        raise ValueError('Reviewed pool metadata does not match original contest values.')
    for label, group in lineups.groupby('lineup', sort=False):
        ids = group.fanduel_id.tolist()
        if len(ids) != 9 or len(set(ids)) != 9 or not set(ids) <= set(pool.index) or Counter(group.slot) != Counter(SLOTS):
            raise ValueError(f'Lineup {label} requires nine unique eligible slots.')
        if any(slot not in allowed_slots(pool.loc[pid].roster_eligibility) for pid, slot in zip(ids, group.slot)):
            raise ValueError(f'Lineup {label} contains an ineligible assignment.')
        eligible = prior.loc[ids].eligible.astype(str).str.casefold().eq('true')
        if not eligible.all() or pool.loc[ids].injury_flag.str.upper().isin({'O', 'OUT', 'INACTIVE', 'IR'}).any():
            raise ValueError(f'Lineup {label} contains an unavailable player.')
        if group.salary.tolist() != pool.loc[ids].salary.tolist() or group.salary.sum() > 60_000:
            raise ValueError(f'Lineup {label} failed the contest salary check.')
        delta = group.adjusted_fd_points.to_numpy() - prior.loc[ids].adjusted_fd_points.to_numpy()
        if not (abs(delta) <= .005000001).all():
            raise ValueError(f'Lineup {label} points do not match the reviewed export.')
        validate_team_roster(contest, ids, require_teams=True)


def review_recovered_contest(source):
    manifest, pool, reviewed, lineups = load_recovered_contest(source)
    verify_recovered_lineups(pool, reviewed, lineups, contest_id=manifest['contest'])
    day = date.fromisoformat(manifest['slate_date'])
    matchups = {matchup_key(game_code(value)) for value in pool.game}
    boxes = collect_final_boxes(day, matchups)
    outcomes, finals = compare_results(reviewed, day, boxes, {})
    scored = lineup_review(lineups, outcomes).rename(columns={
        'Pre-lock projection': 'Reviewed projection', 'Pre-lock absolute error': 'Reviewed absolute error'})
    played = outcomes.loc[outcomes.outcome.eq('Played')].dropna(
        subset=['projected_fd_points', 'adjusted_fd_points', 'nba_fd_points'])
    totals = {
        'contest': manifest['contest'], 'day': day.isoformat(), 'expected_games': len(matchups),
        'final_games': len(finals), 'pool': len(pool), 'outcomes': outcomes.outcome.value_counts().to_dict(),
        'played_projection_comparison': len(played),
        'daily_played_mae': (played.nba_fd_points-played.projected_fd_points).abs().mean() if len(played) else None,
        'reviewed_played_mae': (played.nba_fd_points-played.adjusted_fd_points).abs().mean() if len(played) else None,
        'lineups': scored.round(2).astype(object).where(scored.notna(), None).to_dict('records'),
        'box_sources': sorted(source for _, source in boxes),
        'scope': 'Recovered reviewed candidates. Official entry and verified pre-tip capture are unknown.',
    }
    return totals


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    print(json.dumps(review_recovered_contest(args.archive), indent=2, allow_nan=False))
