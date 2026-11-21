"""Opt-in recurring SQLite backups to a separately mounted durable directory.
Run from cron or a scheduler; NEVER silently assume a container directory is durable.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from history_backup import backup, verify_backup, inspect


def run(source, backup_dir, *, now=None):
    source=Path(source).resolve(strict=True)
    target_dir=Path(backup_dir).resolve(strict=True)
    if not target_dir.is_dir():
        raise NotADirectoryError(target_dir)
    if source.parent==target_dir or source==target_dir:
        raise ValueError('Backups must be in a separate directory')
    # External durability cannot be inferred from the existence of a path.
    timestamp=(now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%S%fZ')
    destination=target_dir/f'player_history_{timestamp}.sqlite'
    manifest=backup(source,destination)
    verified=verify_backup(destination)
    if verified != manifest:
        raise ValueError('Manifest changed during verification')
    return {'path':str(destination),'manifest':str(destination)+'.manifest.json','counts':inspect(destination),'sha256':verified['sha256']}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--backup-dir',required=True,help='MUST be a persistent/mounted storage directory; not Streamlit ephemeral disk')
    args=parser.parse_args()
    print(run(args.source,args.backup_dir))
