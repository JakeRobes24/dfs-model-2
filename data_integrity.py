"""Fail-closed, read-only integrity gate for persisted DFS research inputs."""
from pathlib import Path
import hashlib
import pandas as pd

REQUIRED = {'fanduel_id', 'fanduel_name', 'salary', 'position', 'roster_eligibility', 'adjusted_fd_points'}


def load_research(path, expected_rows=None, expected_sha256=None):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'Research file missing: {path}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError('Research checksum mismatch; refusing to optimize')
    pool = pd.read_csv(path, dtype={'fanduel_id': 'string'})
    missing = REQUIRED - set(pool.columns)
    if missing:
        raise ValueError(f'Research missing columns: {sorted(missing)}')
    if expected_rows is not None and len(pool) != expected_rows:
        raise ValueError(f'Expected {expected_rows} players, found {len(pool)}')
    if pool.fanduel_id.isna().any() or pool.fanduel_id.duplicated().any():
        raise ValueError('Missing or duplicate FanDuel IDs')
    if pool.salary.isna().any() or (pd.to_numeric(pool.salary, errors='coerce') <= 0).any():
        raise ValueError('Invalid player salary')
    if pool.position.isna().any():
        raise ValueError('Missing authoritative positions')
    return pool, {'rows': len(pool), 'columns': len(pool.columns), 'sha256': digest, 'source': str(path)}
