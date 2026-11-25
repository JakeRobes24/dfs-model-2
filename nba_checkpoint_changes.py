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


# These cover the optimizer constraints, objective, emitted player values and
# current status/role warnings. Source metadata remains independently reviewed.
CANDIDATE_FIELDS = ('fanduel_id', *IDENTITY, *DECISIONS, 'adjusted_minutes',
                    'adjusted_fd_points', 'minutes_method', 'injury_flag',
                    'research_attention', 'prelock_change')


def candidate_fingerprint(pool, scope, overlap, exclude, objective):
    """Exact solver-input identity; no rounding, player filtering or tolerance."""
    import hashlib
    import json
    if objective not in ('adjusted_fd_points', 'gpp_objective'):
        raise ValueError('Unknown candidate objective.')
    fields = list(dict.fromkeys((*CANDIDATE_FIELDS, objective)))
    if 'ceiling_fd_points' in pool:
        fields.append('ceiling_fd_points')
    if not set(fields) <= set(pool):
        raise ValueError('Complete candidate inputs required.')
    if pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique:
        raise ValueError('Candidate identity requires distinct player IDs.')
    values = pool[fields].sort_values('fanduel_id', kind='stable')
    header = json.dumps([list(scope), overlap, bool(exclude), objective, fields],
                        separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256((header + '\n' + values.to_csv(index=False)).encode()).hexdigest()


def can_reuse_candidates(result):
    """Only a complete, proven-optimal portfolio and distinct rival may be reused."""
    lineups, comparison, alternative = result
    if lineups.empty or comparison.empty or alternative.empty:
        return False
    if (set(lineups.lineup) != {1,2,3,4}
            or len(lineups) != 36 or len(alternative) != 9
            or not lineups.groupby('lineup').fanduel_id.nunique().eq(9).all()
            or alternative.fanduel_id.nunique() != 9
            or not lineups.solver_optimal.all() or not alternative.solver_optimal.all()
            or not lineups.team_rules_verified.all() or not alternative.team_rules_verified.all()
            or set(comparison['Lineup']) != {1,2,3,4}
            or not comparison['Alternative proven optimal'].all()):
        return False
    return True
