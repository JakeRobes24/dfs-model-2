"""Walk-forward workload, efficiency and dependence checks for paired NFL backs."""
from statistics import mean
from itertools import product

import numpy as np

from nfl_history_baseline_review import WEIGHTS, _paired_games


POLICIES = ('Last-game yards', 'Four-game yards', 'Recent volume × pooled efficiency',
            'Recent volume × shrunk efficiency')


def _game_components(history, player_ids, team, target_day, metric):
    """Keep gaps in the chronology so they cannot extend the lookback."""
    by_day = {row['date']: row for row in history
              if row.get('team') == team and row.get('season_type') == 'regular'
              and row['date'] < target_day}
    volume_key = {'rushing': 'carries', 'receiving': 'targets'}[metric]
    for day, _ in _paired_games(history, player_ids=player_ids, team=team, target_day=target_day):
        row = by_day[day.isoformat()]
        volume = row.get(volume_key, {})
        yards = row.get('yards', {}).get(metric, {})
        if (set(volume) != set(player_ids) or set(yards) != set(player_ids)
                or (metric == 'receiving' and not row.get('target_source'))
                or any(volume[p] is None or yards[p] is None for p in player_ids)):
            yield day, None
            continue
        components = [(volume[p], yards[p]) for p in player_ids]
        if any(type(v) is not int or not 0 <= v <= 60 or type(y) is not int or not -40 <= y <= 330
               or (v == 0 and y != 0) for v, y in components):
            raise ValueError('Invalid player workload or yardage.')
        yield day, components


def empirical_crps(draws, actual):
    """Proper distribution score without Monte Carlo sampling noise."""
    values = np.asarray(draws, dtype=float)
    return float(np.abs(values-actual).mean() - .5*np.abs(values[:, None]-values).mean())


def evaluate_yardage(history, *, player_ids, team, target_day, metric):
    """Hold out every later complete match using four earlier complete rows.

    Volume and efficiency changes are exploratory. The two distributions keep
    identical marginals, varying only whether teammates' game results stay paired.
    """
    if metric not in ('rushing', 'receiving'):
        raise ValueError('Choose rushing or receiving yardage.')
    games = list(_game_components(history, player_ids, team, target_day, metric))
    predictions, simulations = [], []
    for i in range(4, len(games)):
        day, actual = games[i]
        prior = games[i-4:i]
        if actual is None or any(x is None for _, x in prior):
            continue
        volume, yards = np.asarray([x for _,x in prior], dtype=float).transpose(2, 0, 1)
        total_volume = volume.sum(axis=0)
        if (total_volume <= 0).any():
            continue
        pooled_efficiency = yards.sum(axis=0) / total_volume
        pair_efficiency = yards.sum() / total_volume.sum()
        # Shrink each player's four-game observed efficiency toward the pair
        # by 12 carries or 6 targets. Fixed hypotheses, never tuned here.
        pseudo = 12 if metric == 'rushing' else 6
        shrunk = (yards.sum(axis=0) + pseudo*pair_efficiency) / (total_volume + pseudo)
        recent_volume = np.average(volume, axis=0, weights=WEIGHTS['recent'])
        actual_yards = np.asarray([y for _, y in actual])
        estimates = (yards[-1], yards.mean(axis=0), recent_volume*pooled_efficiency, recent_volume*shrunk)
        base = dict(date=day.isoformat(), training_dates=[d.isoformat() for d,_ in prior])
        for policy, forecast in zip(POLICIES, estimates):
            errors = forecast - actual_yards
            predictions.append(dict(**base, policy=policy, actual_yards=actual_yards.tolist(),
                                    predicted_yards=forecast.tolist(),
                                    mae=float(np.abs(errors).mean()), bias=float(errors.mean())))
        for policy, draws in [('Same-game resampling', yards.sum(axis=1)),
                              ('Independent teammate resampling', [a+b for a,b in product(*yards.T)])]:
            lo, hi = np.quantile(draws, [.1,.9])
            total = int(actual_yards.sum())
            simulations.append(dict(**base, policy=policy, actual_pair_yards=total,
                                    expected_pair_yards=float(np.mean(draws)),
                                    crps=empirical_crps(draws,total), interval_width=float(hi-lo),
                                    inside_interval=bool(lo <= total <= hi)))

    def summarize(rows, metrics):
        policies = dict.fromkeys(row['policy'] for row in rows)
        return [dict(policy=p, dates=sum(row['policy']==p for row in rows),
                     **{m:mean(row[m] for row in rows if row['policy']==p) for m in metrics})
                for p in policies]

    return dict(metric=metric, games=len(games), comparison_dates=len(predictions)//len(POLICIES),
                predictions=predictions, simulations=simulations,
                point_summary=summarize(predictions, ('mae','bias')),
                simulation_summary=summarize(simulations, ('crps','interval_width','inside_interval')))


def review_cohorts(cohorts):
    """Reproduce the matched forecast and simulation comparisons by team."""
    return [dict(team=cohort['team'], **evaluate_yardage(
                cohort['history'], player_ids=cohort['player_ids'], team=cohort['team'],
                target_day=cohort['target_day'], metric=metric))
            for cohort in cohorts for metric in ('rushing', 'receiving')]


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path, help='Recorded workload and yardage by cohort')
    args = parser.parse_args()
    print(json.dumps(review_cohorts(json.loads(args.evidence.read_text())['cohorts']), indent=2))
