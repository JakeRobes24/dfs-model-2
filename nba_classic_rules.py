"""Standard NBA classic team rules; historical teamless data is not certified."""
from collections import Counter

MAX_PER_TEAM = 4
MIN_TEAMS = 3


def canonical_teams(pool):
    """Return authoritative normalized team codes, or None for legacy research."""
    if 'team' not in pool:
        if 'identity_match' in pool or 'import_issue' in pool:
            raise ValueError('Contest pool missing authoritative teams')
        return None
    from slate_import import team_code
    teams = pool.team.map(team_code)
    if teams.eq('').any():
        raise ValueError('Contest pool contains missing or invalid team codes')
    return teams


def legal_team_counts(teams):
    counts = Counter(teams)
    return len(counts) >= MIN_TEAMS and max(counts.values(), default=0) <= MAX_PER_TEAM


def validate_team_roster(pool, ids, *, require_teams=False):
    """Reject over-concentrated rosters; return False for teamless legacy data."""
    teams = canonical_teams(pool)
    if teams is None:
        if require_teams:
            raise ValueError('Authoritative contest teams required to certify lineup')
        return False
    lookup = dict(zip(pool.fanduel_id, teams, strict=True))
    if not all(pid in lookup for pid in ids):
        raise ValueError('Unknown contest ID in team validation')
    if not legal_team_counts(lookup[pid] for pid in ids):
        raise ValueError('Invalid team composition: maximum four per team and at least three teams')
    return True
