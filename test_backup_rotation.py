import sqlite3
import tempfile
from pathlib import Path
from backup_rotation import run
from history_backup import verify_backup

def test_rotation():
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp); src=d/'source.sqlite'; target=d/'persistent'; target.mkdir()
        with sqlite3.connect(src) as db:
            for table in ['players','snapshots','snapshot_players','actuals']:
                db.execute(f'CREATE TABLE {table}(id INTEGER)')
                db.execute(f'INSERT INTO {table} VALUES(1)')
        first=run(src,target); second=run(src,target)
        assert first['path'] != second['path']
        assert verify_backup(first['path'])['tables']['players']==1
        assert len(list(target.glob('*.sqlite')))==2
        try: run(src,d/'missing')
        except FileNotFoundError: pass
        else: raise AssertionError('Missing destination accepted')
if __name__=='__main__':
    test_rotation();print('Rotation tests passed')
