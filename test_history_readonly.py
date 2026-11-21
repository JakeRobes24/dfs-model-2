import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from history_readonly import load_history

def test_missing():
    with TemporaryDirectory() as tmp:
        df, status=load_history(Path(tmp)/'absent.sqlite')
        assert df.empty and 'fallback' in status
        assert not (Path(tmp)/'absent.sqlite').exists()

def test_real():
    db=Path(__file__).resolve().parent.parent/'nov20_player_history.sqlite'
    if not db.exists():
        return
    before=db.read_bytes()
    df,status=load_history(db,'2026-11-20')
    assert len(df)==247 and df.fanduel_id.nunique()==247
    assert df.actual_fd_points.notna().sum()==17
    assert db.read_bytes()==before
    other,_=load_history(db,'2026-11-21')
    assert other.empty

if __name__=='__main__':
    test_missing();test_real();print('Read-only history tests passed')
