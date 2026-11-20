"""Convert verified NBA game logs into pre-slate minutes evidence; no fabricated history."""
import pandas as pd

def historical_minutes(game_logs, slate_date, min_games=1):
    """Input player, game_date, minutes, optional started. Excludes slate day and later.
    Only historical completed games strictly before slate date contribute.
    """
    d=game_logs.copy()
    for c in ['player','game_date','minutes']:
        if c not in d:raise ValueError(f'Missing historical column: {c}')
    d['game_date']=pd.to_datetime(d.game_date,errors='coerce')
    d['minutes']=pd.to_numeric(d.minutes,errors='coerce')
    d=d[(d.game_date<pd.Timestamp(slate_date)) & d.minutes.between(0,48)].copy()
    d=d.sort_values('game_date')
    rows=[]
    for player,g in d.groupby('player'):
        if len(g)<min_games:continue
        row={'player':player,'season_mpg':g.minutes.mean(),
             'last5_mpg':g.tail(5).minutes.mean(),
             'last10_mpg':g.tail(10).minutes.mean(),
             'historical_games':len(g),'historical_latest_date':g.game_date.max().date().isoformat()}
        if 'started' in g:row['recent_start_rate']=pd.to_numeric(g.tail(5).started,errors='coerce').mean()
        rows.append(row)
    return pd.DataFrame(rows,columns=['player','season_mpg','last5_mpg','last10_mpg','historical_games','historical_latest_date','recent_start_rate'])
