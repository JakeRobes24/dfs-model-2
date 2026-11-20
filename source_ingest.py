"""Import external historical NBA player game logs with strict point-in-time safeguards.

Supported: Hugging Face cbratkovics parquet, xtheredshirtx FanDuel CSV.
Data are *not* bundled. Caller supplies authentic files downloaded from source.
"""
from pathlib import Path
import pandas as pd
from model import norm
from history_bridge import summarize_logs, bridge_missing
from coverage import VERIFIED_ALIASES

HF_COLS={'player_name':'player','game_date':'game_date','minutes':'minutes','pts':'pts','reb':'reb','ast':'ast','stl':'stl','blk':'blk','tov':'tov'}
FD_COLS={'Player':'player','Date':'game_date','Minutes':'minutes','Points':'pts','Rebounds':'reb','Assists':'ast','Steals':'stl','Blocks':'blk','Turnovers':'tov'}
REQUIRED=['player','game_date','minutes','pts','reb','ast','stl','blk','tov']

def read_logs(path, source='auto'):
    path=Path(path)
    if path.suffix.lower()=='.parquet':
        try: raw=pd.read_parquet(path)
        except ImportError as e: raise ImportError('Install pyarrow to read Parquet: pip install pyarrow') from e
        source='huggingface' if source=='auto' else source
    elif path.suffix.lower()=='.csv':
        raw=pd.read_csv(path)
        source='fanduel_github' if source=='auto' and 'Player' in raw.columns else ('canonical' if source=='auto' else source)
    else:raise ValueError('Expected .csv or .parquet')
    if source=='huggingface': raw=raw.rename(columns=HF_COLS)
    elif source=='fanduel_github':raw=raw.rename(columns=FD_COLS)
    elif source!='canonical':raise ValueError('Unknown source format')
    missing=set(REQUIRED)-set(raw.columns)
    if missing:raise ValueError(f'Missing required game-log fields: {sorted(missing)}')
    d=raw[REQUIRED].copy()
    d['game_date']=pd.to_datetime(d.game_date,errors='coerce')
    if d.game_date.isna().any():raise ValueError('Unparseable game dates')
    for col in REQUIRED[2:]:d[col]=pd.to_numeric(d[col],errors='coerce')
    d['source_dataset']=source
    return d

def join_history_to_contest(coverage, history):
    """Join by explicitly verified aliases, not fuzzy guesswork. Fail on ambiguous keys."""
    h=history.copy();h['key']=h.player.map(norm)
    if h.key.duplicated().any():raise ValueError('Ambiguous historical player keys: review manually')
    c=coverage.copy();c['key']=c.fanduel_name.map(norm)
    c['history_key']=c.key.map(lambda x: VERIFIED_ALIASES.get(x,x))
    return c.merge(h.drop(columns=['player']),left_on='history_key',right_on='key',how='left',suffixes=('','_historical'),validate='many_to_one')

def apply_verified_logs(coverage, path, slate_date='2026-11-20', season_start='2026-10-01'):
    logs=read_logs(path)
    summary=summarize_logs(logs,slate_date,season_start)
    aliases=VERIFIED_ALIASES
    augmented=bridge_missing(coverage,summary,aliases=aliases)
    return augmented,summary
