"""Apply explicitly reviewed hypothetical injury impact inputs without hindsight.

This module does not estimate teammate boosts. It validates independently
obtained conditional projections supplied by the caller. Input timestamps,
source identity and exact contest IDs remain visible in the evidence audit.
"""
from math import isfinite
import pandas as pd

REQUIRED={'out_ids','fanduel_id','source','observed_at','minutes','fd_points'}

def reviewed_impact_pool(pool, out_ids, evidence, as_of, *, max_age_hours=6):
    """Return a separate mean-FD scenario pool and its accepted evidence.

    Each evidence row must refer to the exact simultaneous scratch scenario
    (pipe-delimited contest IDs), one eligible teammate, and an explicitly
    conditional points and minutes projection. Reject ambiguous duplicate rows
    rather than averaging incompatible conditional estimates.
    """
    if not REQUIRED <= set(evidence.columns):
        raise ValueError('Conditional evidence columns missing')
    if not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any():
        raise ValueError('Unique contest IDs required')
    if not isfinite(max_age_hours) or max_age_hours<=0:
        raise ValueError('Positive finite evidence age required')
    cutoff=pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        raise ValueError('As-of requires timezone')
    ids=tuple(out_ids)
    if not ids or len(ids)!=len(set(ids)):
        raise ValueError('Distinct scratch IDs required')
    result=pool.copy(deep=True)
    lookup=result.set_index('fanduel_id')
    if not set(ids)<=set(lookup.index):
        raise ValueError('Unknown scratch ID')
    if not lookup.loc[list(ids),'eligible'].all():
        raise ValueError('Scratch target must be eligible in baseline')
    teams=set(lookup.loc[list(ids),'team'])
    expected=set(map(str,ids))
    notes=evidence.loc[evidence.out_ids.map(lambda x:set(str(x).split('|'))==expected)].copy()
    if notes.fanduel_id.duplicated().any():
        raise ValueError('Ambiguous conditional projections')
    for row in notes.itertuples():
        if row.fanduel_id not in lookup.index or row.fanduel_id in ids:
            raise ValueError('Invalid conditional teammate ID')
        player=lookup.loc[row.fanduel_id]
        if not player.eligible or player.team not in teams:
            raise ValueError('Conditional adjustment must be for an eligible teammate')
        if pd.isna(row.source) or not str(row.source).strip():
            raise ValueError('Conditional source required')
        stamp=pd.Timestamp(row.observed_at)
        if pd.isna(stamp) or stamp.tzinfo is None or not cutoff-pd.Timedelta(hours=max_age_hours)<=stamp<=cutoff:
            raise ValueError('Conditional evidence is undated, stale or future')
        try:
            minutes,points=float(row.minutes),float(row.fd_points)
        except (ValueError,TypeError) as exc:
            raise ValueError('Invalid conditional minutes/points') from exc
        if not all(map(isfinite,(minutes,points))) or not 0<=minutes<=48 or points<0 or (minutes==0 and points!=0):
            raise ValueError('Invalid conditional minutes/points')
        mask=result.fanduel_id.eq(row.fanduel_id)
        result.loc[mask,'adjusted_minutes']=minutes
        result.loc[mask,'adjusted_fd_points']=points
        result.loc[mask,'minutes_method']='reviewed_hypothetical_impact'
    result.loc[result.fanduel_id.isin(ids),'eligible']=False
    return result,notes
