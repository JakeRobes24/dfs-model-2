import tempfile, unittest
from pathlib import Path
from history_backup import backup, inspect
from history_recovery import restore_verified

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        import sqlite3
        self.source = self.root / 'source.sqlite'
        with sqlite3.connect(self.source) as db:
            for t in ['players','snapshots','snapshot_players','actuals']:
                db.execute(f'CREATE TABLE {t} (id INTEGER PRIMARY KEY)')
                db.execute(f'INSERT INTO {t} VALUES (1)')
        self.backup = self.root / 'backup.sqlite'
        backup(self.source,self.backup)

    def test_restore_new_destination(self):
        result = restore_verified(self.backup,self.root/'restored.sqlite')
        self.assertEqual(result['table_counts'],inspect(self.source))

    def test_refuses_overwrite(self):
        with self.assertRaises(FileExistsError):
            restore_verified(self.backup,self.source)

    def test_preserves_destination_created_during_restore(self):
        from unittest.mock import patch

        target = self.root / 'restored.sqlite'
        existing = b'concurrent restore output'

        def publish_loses_race(temp, destination):
            destination.write_bytes(existing)
            raise FileExistsError(destination)

        with patch('history_recovery.os.link', side_effect=publish_loses_race):
            with self.assertRaises(FileExistsError):
                restore_verified(self.backup, target)
        self.assertEqual(target.read_bytes(), existing)

    def test_refuses_tampered_backup(self):
        with open(self.backup,'ab') as f:f.write(b'tamper')
        with self.assertRaises(ValueError):
            restore_verified(self.backup,self.root/'restored.sqlite')
        self.assertFalse((self.root/'restored.sqlite').exists())

if __name__=='__main__':unittest.main()
