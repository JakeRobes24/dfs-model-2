"""Safe offline SQLite recovery: verify source, restore to a NEW path, verify restored bytes and schema."""
from pathlib import Path
import os, sqlite3, tempfile
from history_backup import inspect, sha256, verify_backup


def restore_verified(backup_path, destination):
    source, target = Path(backup_path).resolve(), Path(destination).resolve()
    if source == target:
        raise ValueError('Backup and destination must differ')
    if target.exists() or Path(str(target) + '.manifest.json').exists():
        raise FileExistsError('Refusing to overwrite existing destination')
    manifest = verify_backup(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.restore-', suffix='.sqlite', dir=target.parent)
    os.close(fd)
    try:
        # The verified backup is immutable input. SQLite backup API creates a consistent restored copy.
        with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as src, sqlite3.connect(temp) as dst:
            src.backup(dst)
        if inspect(temp) != manifest['tables']:
            raise ValueError('Restored table counts differ')
        # Publish the completed file atomically. A competing restore keeps its destination.
        restored_sha256 = sha256(temp)
        with open(temp, 'rb') as restored:
            os.fsync(restored.fileno())
        os.link(temp, target)
        return {
            'restored_path': str(target),
            'table_counts': manifest['tables'],
            'restored_sha256': restored_sha256,
        }
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
