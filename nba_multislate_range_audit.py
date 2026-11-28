"""Compare archived NBA range diagnostics on common rosters and equal-weight dates."""
from statistics import mean

from nba_history_roster_ranges import POLICIES


def _paired_rows(rows, keys, common_fields):
    policy_rows = {policy: {} for policy in POLICIES}
    for row in rows:
        policy = row['policy']
        key = tuple(row[field] for field in keys)
        if policy not in policy_rows or key in policy_rows[policy]:
            raise ValueError('Range results require unique rows for known policies.')
        policy_rows[policy][key] = tuple(row[field] for field in common_fields)
    baseline, challenger = (policy_rows[policy] for policy in POLICIES)
    if baseline != challenger:
        raise ValueError('Range policies must score identical lineups and outcomes.')


def _summarize_policy(lineups, pairs):
    below = sum(row['actual'] < row['fd_p10'] for row in lineups)
    above = sum(row['actual'] > row['fd_p90'] for row in lineups)
    inside = len(lineups) - below - above
    brier = [row['brier'] for row in pairs if row['brier'] is not None]
    return dict(
        rosters=len(lineups), inside=inside, below=below, above=above,
        coverage=inside / len(lineups),
        mean_width=mean(row['fd_p90'] - row['fd_p10'] for row in lineups),
        interval_score=mean(row['interval_score'] for row in lineups),
        center_bias=mean(row['reviewed'] - row['actual'] for row in lineups),
        median_bias=mean(row['fd_p50'] - row['actual'] for row in lineups),
        scored_pairs=len(brier),
        order_brier=mean(brier) if brier else None,
    )


def summarize_archived_dates(evaluations):
    """Use one result per exact slate date. Overlapping rosters are descriptive."""
    by_date = {}
    for day, evaluation in sorted(evaluations.items()):
        lineups, pairs = evaluation['lineups'], evaluation['pairs']
        _paired_rows(lineups, ('lineup',), ('actual', 'reviewed'))
        _paired_rows(pairs, ('lineup', 'alternative'), ('actual_gap', 'reviewed_gap'))
        if not lineups:
            continue
        by_date[day] = {
            policy: _summarize_policy(
                [row for row in lineups if row['policy'] == policy],
                [row for row in pairs if row['policy'] == policy],
            ) for policy in POLICIES
        }

    equal_date = {}
    for policy in POLICIES:
        summaries = [row[policy] for row in by_date.values()]
        if summaries:
            average_fields = ('coverage', 'mean_width', 'interval_score', 'center_bias',
                              'median_bias', 'order_brier')
            averages = {}
            for field in average_fields:
                values = [summary[field] for summary in summaries if summary[field] is not None]
                averages[field] = mean(values) if values else None
            counts = ('rosters', 'inside', 'below', 'above', 'scored_pairs')
            equal_date[policy] = dict(
                dates=len(summaries),
                **{field: sum(summary[field] for summary in summaries) for field in counts},
                **averages,
            )
    return dict(by_date=by_date, equal_date=equal_date)
