"""Retrospective NFL target forecasts from exact FTN/nflverse play joins."""
from datetime import date

import pandas as pd

READ_CODES = {'0', '1', '2', 'CHK', 'DES', 'SD'}
FTN_FIELDS = ['nflverse_game_id', 'nflverse_play_id', 'read_thrown', 'date_pulled']
PLAY_FIELDS = ['game_id', 'play_id', 'season_type', 'game_date', 'posteam',
               'play_type', 'pass_attempt', 'two_point_attempt', 'receiver_player_id']
RESULT_FIELDS = ['week', 'date', 'game_id', 'gsis_id', 'position', 'actual', 'baseline',
                 'primary_blend', 'baseline_error', 'primary_error', 'pull_dates_prior']


def charted_target_totals(plays, chart, *, min_coverage=.95):
    """Count charted primary-read targets among actual receiver-directed passes."""
    plays = plays.loc[plays.season_type.eq('REG') & plays.play_type.eq('pass')
                      & plays.pass_attempt.eq(1) & plays.two_point_attempt.eq(0)
                      & plays.receiver_player_id.notna() & plays.posteam.notna()].copy()
    keys = ['game_id', 'play_id']
    # A duplicate makes the team game's coverage ambiguous.
    ambiguous = set(plays.loc[plays.duplicated(keys, keep=False), 'game_id'])
    plays = plays.loc[~plays.game_id.isin(ambiguous)]
    chart = chart.rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'})
    chart = chart.dropna(subset=keys).drop_duplicates(keys, keep=False)
    chart['pulled_at'] = pd.to_datetime(chart.date_pulled, utc=True, errors='coerce', format='mixed')
    joined = plays.merge(chart[keys + ['read_thrown', 'pulled_at']], on=keys,
                         validate='one_to_one', how='left')
    joined['classified'] = (joined.read_thrown.isin(READ_CODES) & joined.pulled_at.notna())
    joined['primary'] = joined.classified & joined.read_thrown.eq('0').fillna(False)
    game_keys = ['game_id', 'posteam']
    totals = joined.groupby(game_keys, as_index=False).agg(
        team_targets=('play_id', 'size'), classified=('classified', 'sum'),
        primary_targets=('primary', 'sum'), pulled_at=('pulled_at', 'max'))
    totals['coverage'] = totals.classified / totals.team_targets
    totals['qualified'] = totals.coverage.ge(min_coverage) & totals.primary_targets.gt(0)
    player = joined.groupby([*game_keys, 'receiver_player_id'], as_index=False).agg(
        play_targets=('play_id', 'size'), player_primary=('primary', 'sum'))
    return totals, player


def compare_target_forecasts(workload, totals, player):
    """Use the same four prior games to test whether primary reads add signal.

    Report which retrospective rows also clear the file's recorded pull dates.
    Pull dates alone do not establish independent historical snapshots.
    """
    by_team = totals.loc[totals.qualified].rename(columns={'posteam': 'team'})
    by_player = player.rename(columns={'posteam': 'team', 'receiver_player_id': 'gsis_id'})
    keys = ['game_id', 'team']
    rows = workload.merge(by_team, on=keys, how='left', validate='many_to_one').merge(
        by_player, on=[*keys, 'gsis_id'], how='left', validate='one_to_one')
    rows[['play_targets', 'player_primary']] = rows[['play_targets', 'player_primary']].fillna(0)
    detail = []
    for _, group in rows.loc[rows.position.isin(['RB', 'WR', 'TE'])].groupby(['gsis_id', 'team']):
        ordered = group.sort_values('team_game_number').to_dict('records')
        for i in range(4, len(ordered)):
            previous, target = ordered[i-4:i], ordered[i]
            number = target['team_game_number']
            if [row['team_game_number'] for row in previous] != list(range(number-4, number)):
                continue
            if any(pd.isna(row['pulled_at']) or row['play_targets'] != row['targets'] for row in previous):
                continue
            observed_targets = sum(row['targets'] for row in previous)
            if observed_targets < 4:
                continue
            baseline = observed_targets / 4
            sample_team_targets = sum(row['team_targets'] for row in previous) / 4
            primary_share = sum(row['player_primary'] for row in previous) / sum(
                row['primary_targets'] for row in previous)
            forecast = (baseline + sample_team_targets * primary_share) / 2
            cutoff = pd.Timestamp(date.fromisoformat(target['gameday']), tz='America/New_York')
            detail.append(dict(
                week=target['week'], date=target['gameday'], game_id=target['game_id'],
                gsis_id=target['gsis_id'], position=target['position'], actual=target['targets'],
                baseline=baseline, primary_blend=forecast,
                baseline_error=abs(baseline-target['targets']), primary_error=abs(forecast-target['targets']),
                pull_dates_prior=all(row['pulled_at'] < cutoff for row in previous)))
    return pd.DataFrame(detail, columns=RESULT_FIELDS)
