"""Research-only walk-forward audit of same-game FanDuel scoring errors."""
import numpy as np
import pandas as pd

from nba_simulation import MINUTE_BANDS, MIN_COHORT, _history_rows
from slate_import import game_code, matchup_key, team_code


def _played_errors(history):
    dates = pd.to_datetime(history.slate_date, errors='coerce').dt.normalize()
    unique = ~history.assign(slate_date=dates).duplicated(['slate_date', 'fanduel_id'], keep=False)
    rows = history.loc[unique & dates.notna()].reset_index(drop=True)
    rows['slate_date'] = pd.to_datetime(rows.slate_date).dt.normalize()
    played = _history_rows(rows)
    played['team'] = rows.loc[played.index, 'team'].map(team_code)
    played['matchup'] = rows.loc[played.index, 'game'].map(game_code).map(matchup_key)
    played['contest'] = played.fanduel_id.astype(str).str.extract(r'^(\d+)-\d+$', expand=False)
    played['error'] = played.actual_points - played.daily_points
    played['band'] = np.digitize(played.daily_minutes, MINUTE_BANDS)
    valid_team = [team in matchup.split('/') for team, matchup in zip(played.team, played.matchup)]
    return played.loc[np.asarray(valid_team, dtype=bool) & played.contest.notna() & played.matchup.ne('')]


def _game_products(rows, prior):
    # Freeze both the location and scale on earlier dates. A later baseline shift
    # can show up as dependence, so these are cross-products, not correlations.
    scale = prior.error.std(ddof=0)
    if not np.isfinite(scale) or scale <= 0:
        return pd.DataFrame(columns=['teammate', 'opponent'])
    offsets = prior.groupby('band').error.agg(['mean', 'size'])
    robust = offsets.loc[offsets['size'].ge(MIN_COHORT), 'mean']
    centered = rows.assign(z=(rows.error - rows.band.map(robust).fillna(prior.error.mean())) / scale)
    games = []
    for (_, matchup), players in centered.groupby(['slate_date', 'matchup']):
        if players.contest.nunique() != 1:
            continue
        teams = [players.loc[players.team.eq(team), 'z'].to_numpy() for team in matchup.split('/')]
        if min(map(len, teams)) < 2:
            continue
        same_team = [(score.sum() ** 2 - (score ** 2).sum()) / (len(score) * (len(score) - 1))
                     for score in teams]
        games.append({'teammate': np.mean(same_team), 'opponent': teams[0].mean() * teams[1].mean()})
    return pd.DataFrame(games, columns=['teammate', 'opponent'])


def walk_forward_dependence(history):
    """Compare prior same-game cross-products with a zero-dependence benchmark.

    Use one saved contest per game and give each game equal weight. The audit is
    conditional on playing, and does not alter the simulator or any rankings.
    """
    played = _played_errors(history)
    reports = []
    for day, heldout in played.groupby('slate_date', sort=True):
        prior = played.loc[played.slate_date.lt(day)]
        if len(prior) < MIN_COHORT:
            continue
        train = _game_products(prior, prior)
        test = _game_products(heldout, prior)
        if train.empty or test.empty:
            continue
        for relationship in ('teammate', 'opponent'):
            predicted = train[relationship].mean()
            observed = test[relationship]
            reports.append({
                'slate_date': day.date().isoformat(), 'relationship': relationship,
                'training_games': len(train), 'test_games': len(test),
                'prior_cross_product': predicted, 'observed_cross_product': observed.mean(),
                'prior_mse': ((observed - predicted) ** 2).mean(),
                'zero_mse': (observed ** 2).mean(),
            })
    return pd.DataFrame(reports)
