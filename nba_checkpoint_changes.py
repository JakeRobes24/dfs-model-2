"""Explain changes between consecutive full-pool research checkpoints."""
import pandas as pd
from slate_import import matchup_key

IDENTITY = ['fanduel_name','team','game','salary','roster_eligibility']
DECISIONS = ['eligible','prelock_status','prelock_starter','prelock_role','confidence']
NUMERIC = ['adjusted_minutes','adjusted_fd_points','ceiling_fd_points']


def compare_checkpoints(previous, current):
    """Compare all contest rows, not just players in the current candidates.

    Any numeric change is retained (rounded only for display). Metadata churn
    cannot be mistaken for a player change. This is advisory, not a cache key
    or a replacement for full optimization or the final injury review.
    """
    for frame in (previous,current):
        if not {'fanduel_id',*IDENTITY,*DECISIONS,*NUMERIC[:2]} <= set(frame):
            raise ValueError('Complete reviewed pools required.')
        if frame.fanduel_id.isna().any() or not frame.fanduel_id.is_unique:
            raise ValueError('Unique player IDs required.')
    old = previous.set_index('fanduel_id')
    new = current.set_index('fanduel_id')
    if set(old.index) != set(new.index):
        raise ValueError('Checkpoint player pools differ.')
    rows = []
    for player in sorted(new.index):
        before, after = old.loc[player], new.loc[player]
        reasons = []
        for field in IDENTITY:
            a,b = before[field],after[field]
            if field == 'game':
                a,b = matchup_key(a),matchup_key(b)
            if str(a) != str(b):
                raise ValueError('Contest identity or eligibility schema changed.')
        for field in DECISIONS:
            a,b = before[field],after[field]
            if str(a if pd.notna(a) else '') != str(b if pd.notna(b) else ''):
                reasons.append(field)
        deltas = {}
        for field in NUMERIC:
            a = pd.to_numeric(before.get(field),errors='coerce')
            b = pd.to_numeric(after.get(field),errors='coerce')
            if pd.isna(a) and pd.isna(b):
                continue
            if pd.isna(a) or pd.isna(b):
                reasons.append(field + ' coverage')
                continue
            if a != b:
                reasons.append(field)
                deltas[field] = float(b-a)
        if reasons:
            rows.append(dict(fanduel_id=player,player=after.fanduel_name,
                             changes='; '.join(reasons),previous_status=before.prelock_status,
                             current_status=after.prelock_status,previous_eligible=before.eligible,
                             current_eligible=after.eligible,
                             minutes_delta=deltas.get('adjusted_minutes'),
                             fd_delta=deltas.get('adjusted_fd_points'),
                             ceiling_delta=deltas.get('ceiling_fd_points')))
    return pd.DataFrame(rows,columns=['fanduel_id','player','changes','previous_status','current_status',
                                      'previous_eligible','current_eligible','minutes_delta','fd_delta','ceiling_delta'])
