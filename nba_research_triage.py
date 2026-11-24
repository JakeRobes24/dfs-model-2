"""Full-pool research triage; never changes scores or eligibility."""
import json
import math
import pandas as pd



def paired_gap_breakdown(daily_points, daily_minutes, encoded):
    """Split each matched provider's point difference into time and rate effects.

    Use symmetric attribution (average of the two rates/minutes) so the terms
    sum exactly to the point gap. Never borrow minutes from another provider.
    The weighted average describes only providers with paired data.
    """
    empty = dict(paired_source_count=0, paired_point_gap=None, time_effect=None,
                 rate_effect=None, paired_gap_driver='Paired evidence unavailable')
    try:
        p, m = float(daily_points), float(daily_minutes)
        notes = json.loads(encoded)
    except (ValueError, TypeError):
        return empty
    if not (math.isfinite(p) and p >= 0 and math.isfinite(m) and 0 < m <= 60
            and isinstance(notes, list)):
        return empty
    rows = []
    families = set()
    for note in notes:
        try:
            points, minutes, weight = (float(note[k]) for k in ('points', 'paired_minutes', 'weight'))
            family = note['family']
            if not isinstance(family, str) or not family or family in families:
                return empty
            if not (0 <= points <= 150 and 0 < minutes <= 60 and 0 < weight <= 1):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        families.add(family)
        rate, baseline_rate = points / minutes, p / m
        time_effect = (minutes - m) * (rate + baseline_rate) / 2
        rate_effect = (rate - baseline_rate) * (minutes + m) / 2
        rows.append((weight, points - p, time_effect, rate_effect))
    if not rows:
        return empty
    total = sum(row[0] for row in rows)
    gap, time, rate = (sum(row[0] * row[i] for row in rows) / total for i in (1, 2, 3))
    if abs(time) < 1 and abs(rate) < 1:
        driver = 'Small paired effects'
    elif time * rate < 0:
        driver = 'Offsetting time and rate effects'
    elif abs(time) >= 2 * abs(rate):
        driver = 'Mainly projected minutes'
    elif abs(rate) >= 2 * abs(time):
        driver = 'Mainly projected production rate'
    else:
        driver = 'Mixed minutes and production rate'
    return dict(paired_source_count=len(rows), paired_point_gap=gap, time_effect=time,
                rate_effect=rate, paired_gap_driver=driver)


def disagreement_queue(scored):
    """Separate provider agreement against DAILY from provider conflict.

    Priority is a transparent research ordering, not a projection or GPP score.
    """
    required = {'fanduel_id','fanduel_name','eligible','projected_fd_points',
                'adjusted_fd_points','independent_fd_points','projection_source_count',
                'projection_source_spread','projected_minutes','independent_minutes',
                'recent_mpg','blend_status','salary'}
    if not required <= set(scored):
        raise ValueError('Full reviewed pool required for disagreement triage.')
    q = scored.loc[scored.eligible.eq(True)].copy()
    q['point_gap'] = q.independent_fd_points - q.projected_fd_points
    q['minute_gap'] = q.independent_minutes - q.projected_minutes
    q['history_gap'] = pd.to_numeric(q.recent_mpg, errors='coerce') - q.projected_minutes
    q['point_gap_pct'] = 100 * q.point_gap / q.projected_fd_points.where(q.projected_fd_points.gt(0))
    q['review_reason'] = ''
    for mask, label in [
        (q.history_gap.abs().gt(5), 'Recent rotation differs from DAILY'),
        (q.minute_gap.abs().gt(5), 'Independent minutes differ from DAILY'),
        (q.point_gap.abs().ge(5) & q.projection_source_count.lt(2), 'Single-source point discrepancy'),
        (q.point_gap.abs().ge(5) & q.projection_source_count.ge(2) &
         q.projection_source_spread.lt(5), 'Agreeing providers differ from DAILY'),
        (q.projection_source_spread.ge(5), 'Independent point providers conflict'),
        (~q.adjusted_fd_points.gt(0), 'Missing usable projection'),
    ]:
        q.loc[mask, 'review_reason'] += label + '; '
    q = q.loc[q.review_reason.ne('')].copy()
    q['research_priority'] = q[['point_gap','minute_gap','history_gap','projection_source_spread']].abs().max(axis=1)
    q.loc[~q.adjusted_fd_points.gt(0), 'research_priority'] = float('inf')
    q['review_reason'] = q.review_reason.str.rstrip('; ')
    breakdown = [paired_gap_breakdown(row.projected_fd_points, row.projected_minutes,
                                      getattr(row, 'projection_sources_json', '[]'))
                 for row in q.itertuples()]
    fields = ['paired_source_count', 'paired_point_gap', 'time_effect', 'rate_effect', 'paired_gap_driver']
    for field in fields:
        q[field] = [row[field] for row in breakdown]
    columns = ['fanduel_id','fanduel_name','salary','projected_fd_points','independent_fd_points',
               'adjusted_fd_points','point_gap','point_gap_pct','projection_source_count',
               'projection_source_spread','projected_minutes','independent_minutes','recent_mpg',
               'minute_gap','history_gap','blend_status','review_reason', *fields, 'research_priority']
    return q.sort_values(['research_priority','fanduel_id'], ascending=[False,True])[columns]
