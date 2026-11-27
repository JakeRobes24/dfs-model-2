"""Chronological FanDuel skill-position research from historical ffopportunity components."""
import pandas as pd

COMPONENTS = {
    'receiving': {'receptions': .5, 'rec_yards_gained': .1, 'rec_touchdown': 6, 'rec_two_point_conv': 2},
    'rushing': {'rush_yards_gained': .1, 'rush_touchdown': 6, 'rush_two_point_conv': 2},
}
MATCH_FIELDS = {
    'receiving': ('targets', 'receiving_yards', 'rec_attempt', 'rec_yards_gained'),
    'rushing': ('carries', 'rushing_yards', 'rush_attempt', 'rush_yards_gained'),
}
DETAIL_FIELDS = ['date', 'week', 'team', 'game_id', 'gsis_id', 'position', 'channel',
                 'policy', 'actual', 'forecast', 'absolute_error']


def matched_opportunity(workload, weekly, *, season, channel):
    """Keep the workload cohort and annotate only matching scoring components."""
    keys = ['gsis_id', 'team', 'game_id', 'week', 'position']
    volume, yards, provider_volume, provider_yards = MATCH_FIELDS[channel]
    weights = COMPONENTS[channel]
    expected = {f'{field}_exp': value for field, value in weights.items()}
    fields = [*weights, *expected]
    non_yardage = [field for field in fields if 'yards' not in field]
    history = weekly.loc[weekly.season.eq(season)].rename(columns={'player_id': 'gsis_id', 'posteam': 'team'})
    history = history.dropna(subset=keys).drop_duplicates(keys[:-1], keep=False)
    matched = workload.merge(history[[*keys, provider_volume, *fields]], how='left',
                             on=keys, validate='one_to_one')
    matched = matched.loc[matched.position.isin(['RB', 'WR', 'TE'])].copy()
    valid = (matched[volume].eq(matched[provider_volume]) & matched[yards].eq(matched[provider_yards])
             & matched[fields].abs().le(350).all(axis=1) & matched[non_yardage].ge(0).all(axis=1))
    matched['actual_fd'] = matched[list(weights)].mul(weights).sum(axis=1, min_count=len(weights)).where(valid)
    matched['expected_fd'] = matched[list(expected)].mul(expected).sum(axis=1, min_count=len(weights)).where(valid)
    return matched


def compare_expected_opportunity(workload, weekly, *, season):
    """Hold opportunity history fixed and compare actual vs expected fantasy output.

    Uses exact historical regular-season joins and identical prior/target rows for
    each policy. Yardage and volume must agree with the independent workload
    join. This compares receiving and rushing scoring without fumbles.
    """
    result = []
    coverage = {}
    for channel in COMPONENTS:
        volume = MATCH_FIELDS[channel][0]
        matched = matched_opportunity(workload, weekly, season=season, channel=channel)
        coverage[channel] = int(matched.actual_fd.notna().sum())
        for _, player in matched.groupby(['gsis_id', 'team']):
            games = player.sort_values('team_game_number').to_dict('records')
            for i in range(4, len(games)):
                prior, target = games[i-4:i], games[i]
                seq = target['team_game_number']
                if [row['team_game_number'] for row in prior] != list(range(seq-4, seq)):
                    continue
                if not all(pd.notna(row['actual_fd']) for row in [*prior, target]):
                    continue
                if sum(row[volume] for row in prior) < 4:
                    continue
                actual_mean = sum(row['actual_fd'] for row in prior)/4
                expected_mean = sum(row['expected_fd'] for row in prior)/4
                for policy, forecast in [('Actual scoring average', actual_mean),
                                         ('Expected scoring average', expected_mean),
                                         ('Equal actual and expected blend', (actual_mean+expected_mean)/2)]:
                    result.append(dict(date=target['gameday'], week=target['week'], team=target['team'],
                                       game_id=target['game_id'], gsis_id=target['gsis_id'], position=target['position'],
                                       channel=channel, policy=policy, actual=target['actual_fd'],
                                       forecast=forecast, absolute_error=abs(forecast-target['actual_fd'])))
    return pd.DataFrame(result, columns=DETAIL_FIELDS), coverage
