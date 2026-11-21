import sqlite3, tempfile
from pathlib import Path
from history_backup import backup,verify_backup,inspect

def test_backup():
    source=Path(__file__).resolve().parent.parent/'nov20_player_history.sqlite'
    with tempfile.TemporaryDirectory() as d:
        out=Path(d)/'snapshot.sqlite'
        counts=inspect(source)
        manifest=backup(source,out)
        assert manifest['tables']==counts
        assert verify_backup(out)==manifest
        try: backup(source,out)
        except FileExistsError: pass
        else: raise AssertionError('Overwrite must be rejected')
        with sqlite3.connect(out) as db:
            db.execute("UPDATE players SET latest_name='corrupted_test' WHERE rowid=1")
            db.commit()
        try: verify_backup(out)
        except ValueError: pass
        else: raise AssertionError('Tampering must be detected')

if __name__=='__main__':
    test_backup()
    print('Verified backup, overwrite refusal, and tamper detection passed')
