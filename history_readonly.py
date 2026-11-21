"""Read-only historical snapshots for Streamlit. No database creation or mutation."""
import sqlite3
from pathlib import Path
import pandas as pd


def load_history(db_path, slate_date=None):
    """Return (rows, status). Missing/unusable history is explicit, never fabricated."""
    path = Path(db_path)
    if not path.is_file():
        return pd.DataFrame(), 'History database unavailable; use verified CSV fallback.'
    try:
        uri = f'{path.resolve().as_uri()}?mode=ro'
        with sqlite3.connect(uri, uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            required = {'players','snapshots','snapshot_players','actuals'}
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required <= tables:
                return pd.DataFrame(), 'History schema incomplete; use verified CSV fallback.'
            columns = '''SELECT s.slate_date, sp.snapshot_id, sp.fanduel_id, sp.name,
                     sp.salary, sp.position, sp.adjusted_fd_points, sp.projected_minutes,
                     sp.adjusted_minutes, a.actual_minutes, a.actual_fd_points, a.source AS actuals_source
                     '''
            joins = '''FROM snapshot_players sp JOIN snapshots s ON s.snapshot_id=sp.snapshot_id
                     LEFT JOIN actuals a ON a.slate_date=s.slate_date AND a.fanduel_id=sp.fanduel_id'''
            if 'actuals_verification' in tables:
                columns += ''', v.status AS outcome, v.nba_status, v.source AS official_source,
                              v.official_minutes, v.official_fd_points, v.prior_comparison '''
                joins += ''' LEFT JOIN actuals_verification v
                           ON v.slate_date=s.slate_date AND v.fanduel_id=sp.fanduel_id'''
            sql = columns + joins
            args = ()
            if slate_date:
                sql += ' WHERE s.slate_date=?'
                args = (slate_date,)
            sql += ' ORDER BY s.slate_date, sp.fanduel_id'
            frame = pd.read_sql_query(sql, db, params=args)
            return frame, ('History loaded (read-only).' if not frame.empty else 'No history for requested slate; use verified CSV fallback.')
    except (sqlite3.Error, OSError, ValueError) as exc:
        return pd.DataFrame(), f'History could not be read ({type(exc).__name__}); use verified CSV fallback.'
