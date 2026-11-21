"""Fetch historical season logs, preserve source provenance, and audit full-pool coverage.

Run in an environment with outbound internet access:
 python fetch_and_audit.py --coverage nov20_complete_247_player_coverage.csv --out audit_output
Or provide a downloaded authentic file with --local-logs PATH.
"""
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
import pandas as pd
from source_ingest import read_logs
from history_bridge import summarize_logs, bridge_missing
from pool_coverage import VERIFIED_ALIASES

SOURCE = 'https://huggingface.co/datasets/cbratkovics/nba-game-logs/resolve/main/game_logs/game_logs_2026-27.parquet'

def download(destination: Path, url=SOURCE):
    destination.parent.mkdir(parents=True,exist_ok=True)
    req=Request(url,headers={'User-Agent':'DFSModel2-HistoricalResearch/0.6'})
    with urlopen(req,timeout=35) as response, destination.open('wb') as out:
        import shutil
        shutil.copyfileobj(response,out)
    if destination.stat().st_size < 1000:
        raise ValueError('Download suspiciously small; inspect source before using')
    return destination

def audit(coverage_path, logs_path, out_dir, slate_date='2026-11-20'):
    out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    coverage=pd.read_csv(coverage_path,dtype={'fanduel_id':str})
    if coverage.fanduel_id.duplicated().any():raise ValueError('Duplicate FanDuel IDs')
    logs=read_logs(logs_path)
    logs=logs[logs.game_date < pd.Timestamp(slate_date)].copy()
    history=summarize_logs(logs,slate_date)
    augmented=bridge_missing(coverage,history,aliases=VERIFIED_ALIASES)
    # Do not count absent/OUT players as optimizable.
    active=~augmented.injury_flag.fillna('').astype(str).str.upper().eq('O')
    report={
      'contest_players':len(coverage),
      'out_excluded':int((~active).sum()),
      'active_players':int(active.sum()),
      'active_with_scoring':int((active & augmented.projected_fd_points.notna()).sum()),
      'active_without_scoring':int((active & augmented.projected_fd_points.isna()).sum()),
      'historical_scoring_fills':int((active & augmented.scoring_provenance.eq('historical_boxscore_estimate')).sum()),
      'historical_log_rows_before_slate':len(logs),
      'history_players':len(history),
      'latest_historical_date':str(logs.game_date.max().date()) if len(logs) else None,
    }
    augmented.to_csv(out_dir/'full_pool_with_historical_evidence.csv',index=False)
    history.to_csv(out_dir/'historical_player_summary.csv',index=False)
    augmented.loc[active & augmented.projected_fd_points.isna()].to_csv(out_dir/'still_missing_scoring.csv',index=False)
    pd.DataFrame([report]).to_csv(out_dir/'coverage_report.csv',index=False)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--coverage',required=True);p.add_argument('--out',default='audit_output');p.add_argument('--local-logs');p.add_argument('--slate-date',default='2026-11-20')
    a=p.parse_args(); out=Path(a.out)
    if a.local_logs:logs=Path(a.local_logs)
    else:
        logs=out/'game_logs_2026-27.parquet'
        if not logs.exists():download(logs)
    print(audit(a.coverage,logs,out,a.slate_date))
if __name__=='__main__':main()
