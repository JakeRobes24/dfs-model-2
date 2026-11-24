"""Post-slate comparison against supplied historical contest entries, not a synthetic field."""
from collections import Counter

import numpy as np
import pandas as pd

from model import SLOTS, allowed_slots
from nba_classic_rules import canonical_teams, legal_team_counts

MAX_FIELD_ENTRIES = 20000


def _rosters(pool, entries, label_column):
    required = {'fanduel_id', 'salary', 'roster_eligibility', 'team'}
    if not required <= set(pool) or not pool.fanduel_id.is_unique:
        raise ValueError('Authoritative unique contest pool and teams required.')
    if not {label_column, 'slot', 'fanduel_id'} <= set(entries) or entries.empty:
        raise ValueError('Entries require an entry label, slot and FanDuel player ID.')
    rows = entries[[label_column, 'slot', 'fanduel_id']].copy()
    if rows.isna().any().any() or rows[label_column].astype(str).str.strip().eq('').any():
        raise ValueError('Entry labels, slots and player IDs cannot be missing.')
    if not rows.fanduel_id.isin(pool.fanduel_id).all():
        raise ValueError('Every player must belong to the exact saved contest pool.')
    metadata = pool.set_index('fanduel_id')
    teams = dict(zip(pool.fanduel_id, canonical_teams(pool)))
    roster = {}
    for label, group in rows.groupby(label_column, sort=False):
        ids = tuple(group.fanduel_id)
        if len(ids) != 9 or len(set(ids)) != 9 or Counter(group.slot) != Counter(SLOTS):
            raise ValueError('Every entry requires all nine slots and nine distinct players.')
        salaries = pd.to_numeric(metadata.loc[list(ids), 'salary'], errors='coerce')
        if (not salaries.between(1, 60000).all() or salaries.sum() > 60000
                or not legal_team_counts(teams[pid] for pid in ids)
                or any(slot not in allowed_slots(metadata.loc[pid, 'roster_eligibility'])
                       for slot, pid in zip(group.slot, ids))):
            raise ValueError('An entry violates salary, roster eligibility or team rules.')
        roster[label] = frozenset(ids)
    return roster


def review_supplied_field(pool, candidates, field, results):
    """Compare saved candidates against one identified sample of real entries.

    Input provenance is user-supplied, not independently authenticated. Duplicate
    rosters with distinct entry IDs count separately. No inference about unseen
    entries, prizes, or true contest rank is made. All required outcomes must be
    resolved from the official results before scores are compared.
    """
    required = {'field_id', 'entry_id', 'source', 'slot', 'fanduel_id'}
    if field.empty or not required <= set(field):
        raise ValueError('Supply field_id, entry_id, source, slot and fanduel_id.')
    if len(field) > 9 * MAX_FIELD_ENTRIES:
        raise ValueError('Use a sample of at most 20,000 historical entries.')
    for col in ('field_id', 'source'):
        values = field[col].astype('string').str.strip()
        if values.isna().any() or values.eq('').any() or values.nunique() != 1:
            raise ValueError('Use one identified contest field and one source.')
    field_rosters = _rosters(pool, field, 'entry_id')
    candidate_rosters = _rosters(pool, candidates, 'lineup')
    fields = {'fanduel_id','outcome','nba_fd_points','nba_source'}
    if not fields <= set(results) or not results.fanduel_id.is_unique:
        raise ValueError('Use unique official player results.')
    resolved = results.nba_source.fillna('').astype(str).str.strip().ne('')
    points = pd.to_numeric(results.nba_fd_points, errors='coerce')
    played = resolved & results.outcome.eq('Played') & np.isfinite(points)
    dnp = resolved & results.outcome.eq('Did not play')
    scores = dict(zip(results.loc[played | dnp, 'fanduel_id'], points.mask(dnp, 0)[played | dnp]))
    needed = set().union(*field_rosters.values(), *candidate_rosters.values())
    if not needed <= scores.keys():
        raise ValueError(f'{len(needed - scores.keys())} required player outcomes unresolved; no field comparison.')
    def total(ids):
        return round(sum(scores[pid] for pid in sorted(ids)), 1)
    field_scores = np.array([total(ids) for ids in field_rosters.values()])
    n = len(field_scores)
    frequencies = Counter(field_rosters.values())
    rows = []
    for label, ids in candidate_rosters.items():
        score = total(ids)
        higher = int((field_scores > score).sum())
        tied = int((field_scores == score).sum())
        lower = n - higher - tied
        rows.append({'Lineup': label, 'Official box-score FD': score,
                     'Supplied entries': n, 'Entries scoring higher': higher,
                     'Entries tied': tied, 'Entries scoring lower': lower,
                     'Sample midrank percentile': 100 * (lower + .5 * tied) / n,
                     'Identical supplied rosters': frequencies[ids],
                     'Sample highest FD': field_scores.max()})
    ownership = Counter(pid for ids in field_rosters.values() for pid in ids)
    exposure = pd.DataFrame({'fanduel_id': pool.fanduel_id})
    exposure['sample_ownership_pct'] = exposure.fanduel_id.map(
        {pid: 100 * count / n for pid,count in ownership.items()}).fillna(0.)
    exposure['field_id'] = field.field_id.iloc[0]
    exposure['source'] = field.source.iloc[0]
    return pd.DataFrame(rows), exposure
