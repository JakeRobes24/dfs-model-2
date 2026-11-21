"""Build an immutable SQLite checkpoint on a durable, restricted backup volume."""
import argparse
import json
import os
import re
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from data_integrity import load_research
from history_backup import backup, verify_backup
from history_recovery import restore_verified
from player_store import connect, import_actuals, import_snapshot

FANDUEL_ID = re.compile(r'\d+-(\d+)')


def identity_review(pool, prior):
    """Recognize exact IDs; record suffix/name matches as candidates without merging."""
    latest = dict(zip(prior.fanduel_id, prior.latest_name, strict=True))
    candidates = {}
    for pid, name in latest.items():
        parsed = FANDUEL_ID.fullmatch(pid)
        if parsed:
            candidates.setdefault(parsed[1], []).append((pid, name))
    records = []
    for row in pool.itertuples():
        pid, name = row.fanduel_id, row.fanduel_name
        parsed = FANDUEL_ID.fullmatch(pid)
        if not parsed:
            raise ValueError(f'Unexpected FanDuel ID: {pid}')
        matches = candidates.get(parsed[1], [])
        exact_name = str(name).strip().casefold()
        if pid in latest:
            if str(latest[pid]).strip().casefold() != exact_name:
                raise ValueError(f'Existing FanDuel ID has a different name: {pid}')
            status, possible = 'existing_exact_id', [pid]
        elif matches and all(str(other).strip().casefold() == exact_name for _, other in matches):
            status, possible = 'cross_slate_candidate', [other_id for other_id, _ in matches]
        elif matches:
            status, possible = 'identity_conflict', [other_id for other_id, _ in matches]
        else:
            status, possible = 'new_player', []
        records.append((pid, name, status, json.dumps(possible)))
    return pd.DataFrame(records, columns=['fanduel_id', 'name', 'identity_status', 'prior_ids'])


def create_checkpoint(source_backup, research, slate_date, output_dir, *, actuals=None):
    """Restore a working copy, review IDs, and publish a new immutable backup pair."""
    slate = date.fromisoformat(slate_date).isoformat()
    root = Path(output_dir).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    pool, meta = load_research(research)
    with TemporaryDirectory(prefix='.dfs-build-', dir=root) as scratch:
        stage = Path(scratch)
        working = stage / 'working.sqlite'
        restore_verified(source_backup, working)
        with closing(connect(working)) as db:
            prior = pd.read_sql_query('SELECT fanduel_id, latest_name FROM players ORDER BY fanduel_id', db)
            review = identity_review(pool, prior)
            conflicts = review.loc[review.identity_status.eq('identity_conflict'), 'fanduel_id'].tolist()
            if conflicts:
                raise ValueError(f'Identity conflicts require review: {conflicts}')
            imported = import_snapshot(db, research, slate, meta['rows'], meta['sha256'])
            if actuals is not None:
                recorded = pd.read_csv(actuals, dtype={'fanduel_id': str})
                if 'fanduel_id' not in recorded or not set(recorded.fanduel_id) <= set(pool.fanduel_id):
                    raise ValueError('Actuals must use IDs in this slate snapshot')
                import_actuals(db, actuals, slate)
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Checkpoint has invalid player references')
        target = stage / 'history.sqlite'
        manifest = backup(working, target)
        verify_backup(target)
        review.to_csv(stage / 'identity_review.csv', index=False)
        (stage / 'import.json').write_text(json.dumps(imported, indent=2) + '\n')
        working.unlink()
        version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination = root / f'{slate}-{version}'
        os.rename(stage, destination)
    return destination, manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True)
    parser.add_argument('--research', required=True)
    parser.add_argument('--slate-date', required=True)
    parser.add_argument('--output-dir', required=True, help='Existing restricted durable volume or upload staging directory')
    parser.add_argument('--actuals')
    options = parser.parse_args()
    result, manifest = create_checkpoint(
        options.backup, options.research, options.slate_date, options.output_dir, actuals=options.actuals,
    )
    print(result)
    print(json.dumps(manifest, indent=2))
