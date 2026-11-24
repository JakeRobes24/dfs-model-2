"""Full-pool research triage; never changes scores or eligibility."""
import pandas as pd


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
    columns = ['fanduel_id','fanduel_name','salary','projected_fd_points','independent_fd_points',
               'adjusted_fd_points','point_gap','point_gap_pct','projection_source_count',
               'projection_source_spread','projected_minutes','independent_minutes','recent_mpg',
               'minute_gap','history_gap','blend_status','review_reason','research_priority']
    return q.sort_values(['research_priority','fanduel_id'], ascending=[False,True])[columns]
