"""Research-only walk-forward audit of same-game FanDuel scoring errors."""
import numpy as np
import pandas as pd

from nba_simulation import MINUTE_BANDS, MIN_COHORT, _history_rows
from slate_import import game_code, matchup_key, team_code


def _played_errors(history, *, reviewed=False):
    dates = pd.to_datetime(history.slate_date, errors='coerce').dt.normalize()
    unique = ~history.assign(slate_date=dates).duplicated(['slate_date', 'fanduel_id'], keep=False)
    rows = history.loc[unique & dates.notna()].reset_index(drop=True)
    rows['slate_date'] = pd.to_datetime(rows.slate_date).dt.normalize()
    played = _history_rows(rows)
    played['team'] = rows.loc[played.index, 'team'].map(team_code)
    played['matchup'] = rows.loc[played.index, 'game'].map(game_code).map(matchup_key)
    played['contest'] = played.fanduel_id.astype(str).str.extract(r'^(\d+)-\d+$', expand=False)
    if reviewed:
        points = pd.to_numeric(rows.loc[played.index, 'adjusted_fd_points'], errors='coerce')
        minutes = pd.to_numeric(rows.loc[played.index, 'adjusted_minutes'], errors='coerce')
        played = played.loc[points.gt(0) & np.isfinite(points) & minutes.gt(0) & minutes.le(48)].copy()
        played['error'] = played.actual_points - points
        played['band'] = np.digitize(minutes.loc[played.index], MINUTE_BANDS)
    else:
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


def walk_forward_dependence(history, *, reviewed=False):
    """Compare prior same-game cross-products with a zero-dependence benchmark.

    Use one saved contest per game and give each game equal weight. The audit is
    conditional on playing, and does not alter the simulator or any rankings.
    """
    played = _played_errors(history, reviewed=reviewed)
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


def reviewed_dependence_evidence(history, target_day):
    """Audit adjusted-score dependence with only earlier complete pre-tip captures.

    Cross-products are not Pearson or copula correlations. Report whether
    earlier estimates improve held-out game errors over zero dependence;
    never convert these diagnostics into simulation weights automatically.
    """
    required = {'slate_date', 'fanduel_id', 'team', 'game', 'eligible',
                'daily_minutes', 'daily_points', 'actual_minutes', 'actual_points',
                'adjusted_minutes', 'adjusted_fd_points', 'verified_outcome', 'nba_source',
                'replay_before_full_slate_tip', 'replay_captured_at_utc', 'replay_cutoff_utc',
                'replay_timing'}
    if not required <= set(history):
        return pd.DataFrame(), pd.DataFrame()
    h = history.copy()
    h['slate_date'] = pd.to_datetime(h.slate_date, errors='coerce').dt.normalize()
    h = h.loc[h.slate_date.lt(pd.Timestamp(target_day).normalize())]
    valid = []
    for day, frame in h.groupby('slate_date', sort=True):
        ids = frame.fanduel_id.astype(str)
        capture = pd.to_datetime(frame.replay_captured_at_utc, utc=True, errors='coerce', format='mixed')
        cutoff = pd.to_datetime(frame.replay_cutoff_utc, utc=True, errors='coerce', format='mixed')
        if (not ids.is_unique or not ids.str.fullmatch(r'[0-9]{1,12}-[0-9]+').all()
                or ids.str.split('-').str[0].nunique() != 1
                or capture.nunique() != 1 or not capture.lt(cutoff).all()
                or not cutoff.dt.tz_convert('America/New_York').dt.date.eq(day.date()).all()
                or not frame.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()
                or not frame.replay_timing.eq('before_scheduled_tip').all()):
            continue
        frame = frame.loc[frame.verified_outcome.eq('played') &
                          frame.nba_source.fillna('').astype(str).str.strip().ne('')].copy()
        frame['eligible'] = frame.eligible.astype(str).str.lower().eq('true')
        valid.append(frame)
    if not valid:
        return pd.DataFrame(), pd.DataFrame()
    detail = walk_forward_dependence(pd.concat(valid, ignore_index=True), reviewed=True)
    summary = []
    if not detail.empty:
        for relationship, group in detail.groupby('relationship', sort=True):
            weights = group.test_games
            prior = np.average(group.prior_mse, weights=weights)
            zero = np.average(group.zero_mse, weights=weights)
            dates = group.slate_date.nunique()
            games = int(weights.sum())
            status = 'Insufficient held-out evidence'
            if dates >= 5 and games >= 30:
                status = 'Requires separate correlation calibration' if prior < zero else 'Zero benchmark not beaten'
            summary.append({'relationship': relationship, 'heldout_dates': dates,
                            'heldout_games': games, 'prior_mse': prior, 'zero_mse': zero,
                            'improved_dates': int(group.prior_mse.lt(group.zero_mse).sum()),
                            'status': status})
    return detail, pd.DataFrame(summary)
