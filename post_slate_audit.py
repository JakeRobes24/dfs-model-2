"""Reproducible post-slate audit. Never adjusts future projections from one slate."""
from pathlib import Path
import pandas as pd


def audit_players(research_csv, lineup_actuals_csv):
    research = pd.read_csv(research_csv)
    scores = pd.read_csv(lineup_actuals_csv)
    required_research = {'fanduel_id','fanduel_name','adjusted_fd_points','adjusted_minutes'}
    required_actual = {'lineup','player','actual_fd'}
    if not required_research.issubset(research) or not required_actual.issubset(scores):
        raise ValueError('Missing required audit columns')
    if research.fanduel_id.duplicated().any():
        raise ValueError('Duplicate FanDuel IDs in research')
    if scores.duplicated(['lineup','player']).any():
        raise ValueError('Duplicate player within a lineup')
    if scores.groupby('lineup').size().ne(9).any():
        raise ValueError('Every audited lineup must have exactly nine players')
    norm=lambda s: ''.join(c for c in str(s).casefold() if c.isalnum())
    research=research.assign(match_key=research.fanduel_name.map(norm))
    if research.match_key.duplicated().any():
        raise ValueError('Ambiguous normalized names; resolve using FanDuel IDs')
    grouped=scores.groupby('player',as_index=False).agg(actual_fd=('actual_fd','first'),exposures=('lineup','nunique'))
    if scores.groupby('player').actual_fd.nunique().gt(1).any():
        raise ValueError('Conflicting actual points for same player')
    grouped['match_key']=grouped.player.map(norm)
    result=grouped.merge(research[['match_key','fanduel_id','fanduel_name','adjusted_fd_points','adjusted_minutes']],on='match_key',how='left',validate='one_to_one')
    if result.fanduel_id.isna().any():
        raise ValueError('Unmatched players: '+', '.join(result.loc[result.fanduel_id.isna(),'player']))
    result['error_fd']=result.actual_fd-result.adjusted_fd_points
    result['abs_error_fd']=result.error_fd.abs()
    result['portfolio_error_fd']=result.error_fd*result.exposures
    return result.sort_values('portfolio_error_fd')

if __name__ == '__main__':
    root=Path(__file__).resolve().parent
    folder=root.parent
    audit_players(root/'data/nov20_research_v33_full.csv',folder/'Nov20_Post_Slate_Player_Scores.csv').to_csv(folder/'Nov20_Reproducible_Audit.csv',index=False)
