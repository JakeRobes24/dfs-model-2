"""Explicit, verified, offline SQLite backup/restore; never writes to live database."""
from pathlib import Path
import hashlib, json, os, sqlite3, tempfile
from datetime import datetime, timezone

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def inspect(path):
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError(p)
    with sqlite3.connect(f'{p.resolve().as_uri()}?mode=ro',uri=True) as db:
        check=db.execute('PRAGMA integrity_check').fetchone()[0]
        if check!='ok': raise ValueError(f'Integrity check failed: {check}')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        needed={'players','snapshots','snapshot_players','actuals'}
        if not needed<=tables: raise ValueError('Missing required tables')
        return {table:db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in sorted(needed)}

def backup(source,destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if source==destination: raise ValueError('Source and destination must differ')
    if destination.exists(): raise FileExistsError('Refusing to overwrite backup')
    before=inspect(source)
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.history-backup-',suffix='.sqlite',dir=destination.parent)
    os.close(fd)
    try:
        with sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True) as src, sqlite3.connect(tmp) as dst:
            src.backup(dst)
        after=inspect(tmp)
        if before!=after: raise ValueError('Backup counts differ')
        os.replace(tmp,destination)
        manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'sha256':sha256(destination),'tables':after,'source_name':source.name}
        manifest_path=Path(str(destination)+'.manifest.json')
        if manifest_path.exists(): raise FileExistsError('Manifest already exists')
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        return manifest
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def verify_backup(destination):
    p=Path(destination)
    manifest=json.loads(Path(str(p)+'.manifest.json').read_text())
    if sha256(p)!=manifest['sha256']: raise ValueError('Backup checksum mismatch')
    if inspect(p)!=manifest['tables']: raise ValueError('Backup counts mismatch')
    return manifest
