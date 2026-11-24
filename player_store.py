"""Local, auditable DFS history store. SQLite file must live on persistent disk in production."""
import hashlib
from math import isfinite
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from data_integrity import load_research

SCHEMA = '''
CREATE TABLE IF NOT EXISTS players (fanduel_id TEXT PRIMARY KEY, latest_name TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, slate_date TEXT NOT NULL, source_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, player_count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS snapshot_players (snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id), fanduel_id TEXT NOT NULL REFERENCES players(fanduel_id), name TEXT NOT NULL, salary REAL NOT NULL, position TEXT NOT NULL, adjusted_fd_points REAL, projected_minutes REAL, adjusted_minutes REAL, raw_json TEXT NOT NULL, PRIMARY KEY(snapshot_id,fanduel_id));
CREATE TABLE IF NOT EXISTS actuals (slate_date TEXT NOT NULL, fanduel_id TEXT NOT NULL REFERENCES players(fanduel_id), actual_minutes REAL, actual_fd_points REAL, source TEXT, recorded_at TEXT NOT NULL, PRIMARY KEY(slate_date,fanduel_id));
'''

def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    return db

def _str(value):
    return '' if pd.isna(value) else str(value)

def _number(value):
    return None if pd.isna(value) or str(value).strip()=='' else float(value)

def import_snapshot(db, csv_path, slate_date, expected_rows=None, expected_sha256=None):
    pool, meta = load_research(csv_path, expected_rows, expected_sha256)
    snapshot_id = hashlib.sha256((slate_date + ':' + meta['sha256']).encode()).hexdigest()[:24]
    existing = db.execute('SELECT snapshot_id FROM snapshots WHERE snapshot_id=?',(snapshot_id,)).fetchone()
    if existing:
        return {'snapshot_id':snapshot_id,'status':'already_imported','players':len(pool),'new_players':0}
    now = datetime.now(timezone.utc).isoformat()
    prior_ids = {x[0] for x in db.execute('SELECT fanduel_id FROM players')}
    new_ids = set(pool.fanduel_id.astype(str)) - prior_ids
    with db:
        db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?)',(snapshot_id,slate_date,meta['sha256'],now,len(pool)))
        for _, row in pool.iterrows():
            pid, name = str(row['fanduel_id']), str(row['fanduel_name'])
            db.execute('INSERT INTO players VALUES (?,?,?,?) ON CONFLICT(fanduel_id) DO UPDATE SET latest_name=excluded.latest_name,last_seen=excluded.last_seen',(pid,name,slate_date,slate_date))
            raw = {str(k): (None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in row.items()}
            db.execute('INSERT INTO snapshot_players VALUES (?,?,?,?,?,?,?,?,?)',(snapshot_id,pid,name,float(row.salary),str(row.position),_number(row.adjusted_fd_points),_number(row.get('projected_minutes')),_number(row.get('adjusted_minutes')),json.dumps(raw,default=str)))
    return {'snapshot_id':snapshot_id,'status':'imported','players':len(pool),'new_players':len(new_ids),'new_player_ids':sorted(new_ids)}

def import_actuals(db, csv_path, slate_date, allow_overwrite=False):
    data = pd.read_csv(csv_path,dtype={'fanduel_id':'string'})
    required = {'fanduel_id','actual_minutes','actual_fd_points'}
    if not required.issubset(data.columns):
        raise ValueError(f'Missing actuals columns: {sorted(required-set(data.columns))}')
    if data.fanduel_id.isna().any() or data.fanduel_id.duplicated().any():
        raise ValueError('Missing or duplicate actuals player IDs')
    recorded = 0
    skipped = 0
    unchanged = 0
    now = datetime.now(timezone.utc).isoformat()
    with db:
        for _, row in data.iterrows():
            minutes, points = _number(row.actual_minutes),_number(row.actual_fd_points)
            if minutes is None and points is None:
                skipped += 1
                continue
            pid = str(row.fanduel_id)
            if not db.execute('''SELECT 1 FROM snapshot_players sp
                                 JOIN snapshots s ON s.snapshot_id=sp.snapshot_id
                                 WHERE s.slate_date=? AND sp.fanduel_id=?''',(slate_date,pid)).fetchone():
                raise ValueError(f'Unknown FanDuel ID in actuals for this slate: {pid}')
            if ((minutes is not None and (not isfinite(minutes) or minutes < 0))
                    or (points is not None and not isfinite(points))):
                raise ValueError(f'Invalid actual numeric result for {pid}')
            source = _str(row.get('actuals_source',''))
            previous = db.execute('SELECT actual_minutes,actual_fd_points,source FROM actuals WHERE slate_date=? AND fanduel_id=?',(slate_date,pid)).fetchone()
            if previous and previous[:2] == (minutes,points):
                # Preserve original provenance and timestamp on identical retry.
                # Explicit correction may update the source if approved.
                if not allow_overwrite or previous[2] == source:
                    unchanged += 1
                    continue
            if previous and previous[:2] != (minutes,points) and not allow_overwrite:
                raise ValueError(f'Conflicting actuals for {pid}; manual approval required')
            db.execute('INSERT INTO actuals VALUES (?,?,?,?,?,?) ON CONFLICT(slate_date,fanduel_id) DO UPDATE SET actual_minutes=excluded.actual_minutes,actual_fd_points=excluded.actual_fd_points,source=excluded.source,recorded_at=excluded.recorded_at',(slate_date,pid,minutes,points,source,now))
            recorded += 1
    return {'recorded':recorded,'skipped_without_results':skipped,'unchanged':unchanged}

def audit_summary(db, slate_date):
    return db.execute('''SELECT COUNT(*),SUM(CASE WHEN a.actual_fd_points IS NOT NULL THEN 1 ELSE 0 END),SUM(CASE WHEN a.actual_minutes IS NOT NULL THEN 1 ELSE 0 END) FROM snapshot_players sp JOIN snapshots s ON sp.snapshot_id=s.snapshot_id LEFT JOIN actuals a ON a.slate_date=s.slate_date AND a.fanduel_id=sp.fanduel_id WHERE s.slate_date=?''',(slate_date,)).fetchone()
