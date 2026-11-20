"""Point-in-time, auditable historical NBA game-log bridge for DFS Model 2.0.

Only accepts real, supplied records. Never treats an absent historical row as zero.
"""
import pandas as pd
import numpy as np
from model import norm

FD_WEIGHTS={'pts':1.,'reb':1.2,'ast':1.5,'stl':3.,'blk':3.,'tov':-1.}

def summarize_logs(logs, slate_date, season_start='2026-10-01'):
    required=['player','game_date','minutes',*FD_WEIGHTS]
    missing=[c for c in required if c not in logs.columns]
    if missing:raise ValueError('Historical logs missing '+', '.join(missing))
    d=logs.copy()
    d['game_date']=pd.to_datetime(d.game_date,errors='coerce')
    cutoff=pd.Timestamp(slate_date)
    d=d[(d.game_date<cutoff)&(d.game_date>=pd.Timestamp(season_start))].copy()
    for c in ['minutes',*FD_WEIGHTS]:d[c]=pd.to_numeric(d[c],errors='coerce')
    # Require complete statistical rows; a DNP with zero minutes must not skew active-game rates.
    d=d[d.minutes.between(1,60)&d[list(FD_WEIGHTS)].notna().all(axis=1)].copy()
    if d.empty:return pd.DataFrame(columns=['player','season_mpg','last5_mpg','last10_mpg','historical_games','historical_fppm','historical_fdpg','historical_latest_date','historical_provenance'])
    d['fd_points']=sum(d[c]*w for c,w in FD_WEIGHTS.items())
    d['key']=d.player.map(norm)
    d=d.sort_values('game_date')
    records=[]
    for key,g in d.groupby('key'):
        total_min=g.minutes.sum()
        records.append(dict(player=g.player.iloc[-1],key=key,season_mpg=g.minutes.mean(),last5_mpg=g.tail(5).minutes.mean(),last10_mpg=g.tail(10).minutes.mean(),historical_games=len(g),historical_fppm=g.fd_points.sum()/total_min,historical_fdpg=g.fd_points.mean(),historical_latest_date=g.game_date.max().date().isoformat(),historical_provenance='user_supplied_verified_logs'))
    return pd.DataFrame(records)

def bridge_missing(coverage, history, aliases=None, minimum_games=3):
    """Fill *only* previously missing scoring rows, requiring actual multi-game box scores.
    Missing player IDs and names remain unresolved; no fuzzy automatic joins.
    """
    d=coverage.copy();h=history.copy()
    if 'key' not in h:h['key']=h.player.map(norm)
    d['key']=d.fanduel_name.map(norm)
    aliases=aliases or {}
    d['history_key']=d.key.map(lambda k: aliases.get(k,k))
    cols=['key','historical_games','historical_fppm','season_mpg','last5_mpg','last10_mpg','historical_latest_date','historical_provenance']
    d=d.merge(h[cols].rename(columns={'key':'history_key'}),on='history_key',how='left',validate='many_to_one')
    missing=d.projected_fd_points.isna() & ~d.injury_flag.fillna('').astype(str).str.upper().eq('O')
    supported=missing & d.historical_games.ge(minimum_games) & d.historical_fppm.gt(0)
    # Estimate minutes from observed rotations; do not fabricate scoring for unobserved players.
    est_minutes=.65*d.last5_mpg+.35*d.season_mpg
    d.loc[supported,'projected_minutes']=est_minutes[supported]
    d.loc[supported,'projected_fd_points']=est_minutes[supported]*d.loc[supported,'historical_fppm']
    d['scoring_provenance']=np.where(supported,'historical_boxscore_estimate',np.where(d.projected_fd_points.notna(),'DAILY','unresolved'))
    d['scoring_confidence']=np.where(supported & d.historical_games.ge(10),'medium',np.where(supported,'low',np.where(d.projected_fd_points.notna(),'DAILY_baseline','missing')))
    d['needs_manual_review']=d.scoring_provenance.eq('unresolved') & ~d.injury_flag.fillna('').astype(str).str.upper().eq('O')
    return d
