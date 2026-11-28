"""Reconstruct the exact saved November 27 portfolio simulation for auditing."""
from itertools import combinations
import re
import unicodedata

import numpy as np
import pandas as pd

from nba_classic_rules import legal_team_counts
from slate_import import team_code

SLOTS = ('PG', 'SG', 'SF', 'PF', 'C', 'G/F', 'F/C', 'UTIL', 'UTIL')
SCENARIOS = ('in', 'all_q_out')
QUANTILES = (.1, .5, .9)
ANCHOR = 'Karl-Anthony Towns'
CONTEST = '137257'


def _historic_key(name):
    # Retain the exact archived simulator's name normalization for replay.
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'(jr|iii|ii)$', '', re.sub(r'[^a-z0-9]', '', name))


def _member_indices(roster, pool, *, candidate=False):
    indices, players = roster['indices'], roster['players']
    if (len(indices) != len(SLOTS) or len(set(indices)) != len(SLOTS)
            or len(players) != len(SLOTS)
            or any(type(i) is not int or i not in pool.index for i in indices)):
        raise ValueError('Invalid saved roster indices.')
    members = pool.loc[indices]
    if list(members.id) != [p['id'] for p in players]:
        raise ValueError('Roster ID does not match the archived ordered pool.')
    if candidate:
        if (tuple(p['slot'] for p in players) != SLOTS
                or members.salary.sum() != roster['salary'] or roster['salary'] > 60000):
            raise ValueError('Invalid archived roster slots or salary.')
        for slot, row in zip(SLOTS, members.itertuples(index=False), strict=True):
            fields = row.eligibility if slot in ('G/F', 'F/C', 'UTIL') else row.position
            if (f'/{slot}/' not in f'/{fields}/'
                    or row.status_1715 not in ('', 'P', 'A')):
                raise ValueError('Archived candidate is outside the saved eligibility.')
        clubs = members.team.map(team_code)
        if clubs.eq('').any() or not legal_team_counts(clubs):
            raise ValueError('Archived candidate violates team limits.')
        if any(not np.isclose(roster[s], members[f'{s}_fd'].sum(), atol=1e-8, rtol=0)
               for s in SCENARIOS):
            raise ValueError('Archived scenario totals disagree with the player pool.')
    return indices


def _historic_residuals(observations, pool, indices):
    prior = pd.DataFrame(observations)
    prior = prior.loc[prior.game_date.lt('2026-11-27') & prior.minutes.gt(0)].copy()
    prior['fd'] = (prior.points+1.2*prior.reboundsTotal+1.5*prior.assists
                   +3*prior.steals+3*prior.blocks-prior.turnovers)
    prior = prior.sort_values('game_date')
    prior['team'] = prior.team.replace({'NYK':'NY', 'PHX':'PHO'})
    prior['key'] = prior.player.map(_historic_key)
    residuals = {}
    # Original RNG allocation depended on iteration over this exact int set.
    for i in set(indices):
        player = pool.loc[i]
        rows = prior.loc[prior.team.eq(player.team) & prior.key.eq(_historic_key(player.player))].tail(8)
        if len(rows) >= 4:
            minutes = rows.minutes.to_numpy()
            rates = rows.fd.to_numpy()/minutes
            draws = (minutes[:, None]*rates[None, :]).ravel()
            residuals[i] = draws-draws.mean()
    return residuals


def _sample(residuals, candidates, seed, size):
    rng = np.random.default_rng(seed)
    sampled = {i:rng.choice(values, size) for i, values in residuals.items()}
    return np.array([sum(sampled[i] for i in roster) for roster in candidates])


def _best_mean(indices, scenarios, residuals):
    return min(float((residuals[indices]+means[indices, None]).max(axis=0).mean())
               for means in scenarios)


def score_range(draws, actual):
    """Leave score metrics missing when a played outcome cannot be certified."""
    low, median, high = np.quantile(draws, QUANTILES)
    result = dict(p10=float(low), p50=float(median), p90=float(high))
    if actual is None:
        return dict(result, actual=None, covered=None, below=None, above=None, interval_score=None)
    score = high-low+10*max(low-actual, 0)+10*max(actual-high, 0)
    return dict(result, actual=float(actual), covered=bool(low<=actual<=high),
                below=bool(actual<low), above=bool(actual>high), interval_score=float(score))


def replay_nov27_portfolios(pool, closing_report, earlier_report, history, outcomes):
    """Recover saved draws without rerunning optimization or fitting outcomes."""
    if (str(closing_report.get('contest')) != CONTEST
            or str(earlier_report.get('contest')) != CONTEST
            or not pool.index.equals(pd.RangeIndex(len(pool)))
            or not pool.id.is_unique or not pool.id.str.fullmatch(CONTEST+r'-\d+').all()):
        raise ValueError('Expected the original ordered November 27 contest pool.')
    pool = pool.assign(status_1715=pool.status_1715.fillna(''))
    archived = list(closing_report['candidates'].items())
    candidates = [_member_indices(roster, pool, candidate=True) for _, roster in archived]
    extra = earlier_report['previous']+[closing_report['personal']]
    residuals = _historic_residuals(history, pool, [i for roster in candidates for i in roster]
                                   +[i for roster in extra for i in _member_indices(roster, pool)])
    if any(i not in residuals for roster in candidates for i in roster):
        raise ValueError('Historical inputs do not reproduce the saved eligible candidate set.')
    selected = [_member_indices(roster, pool, candidate=True) for roster in closing_report['selected']]
    selected_idx = [candidates.index(roster) for roster in selected]
    anchor, = pool.index[pool.player.eq(ANCHOR)]
    anchor_in = [i for i, roster in enumerate(candidates) if anchor in roster]
    anchor_out = [i for i, roster in enumerate(candidates) if anchor not in roster]
    means = np.array([[row[s] for _,row in archived] for s in SCENARIOS])
    points_first = (sorted(anchor_in, key=lambda i:-means[0,i])[:2]
                    + sorted(anchor_out, key=lambda i:-means[0,i])[:2])
    threshold = means[0, points_first].sum()-4
    portfolios = [list(a+b) for a in combinations(anchor_in, 2) for b in combinations(anchor_out, 2)
                  if means[0, list(a+b)].sum() >= threshold]
    training = _sample(residuals, candidates, 1840137257, 2500)
    test = _sample(residuals, candidates, 1841137257, 30000)
    recovered = max(portfolios, key=lambda ids:_best_mean(ids, means, training))
    metadata = dict(count=len(archived), sim_eligible=len(candidates), portfolios=len(portfolios), draws=len(test[0]),
                    top_points=float(means[0, points_first].sum()),selected_points=float(means[0, selected_idx].sum()),
                    top_points_robust_mean_best=_best_mean(points_first, means, test),
                    selected_robust_mean_best=_best_mean(selected_idx, means, test))
    if (set(recovered) != set(selected_idx) or len(recovered) != len(set(selected_idx))
            or any(not np.isclose(value, closing_report['comparison'][key], atol=1e-8, rtol=0)
                   for key,value in metadata.items())):
        raise ValueError('Saved selection or aggregate receipts could not be reproduced.')

    # The complete outcome table is scored only after reproducing the archive.
    if not outcomes.id.is_unique or not set(outcomes.id) <= set(pool.id):
        raise ValueError('Joined outcomes must have unique exact contest identities.')
    observed = outcomes.set_index('id')
    distribution = test+means[0,:,None]
    rows = []
    for idx, indices in enumerate(candidates):
        scored = observed.reindex(pool.loc[indices, 'id'])
        actual = scored.actual.sum() if scored.played.eq(True).all() and np.isfinite(scored.actual).all() else None
        rows.append(dict(candidate=archived[idx][0], projected=float(means[0,idx]),
                         entered=idx in selected_idx, points_first=idx in points_first,
                         **score_range(distribution[idx], actual)))
    result = pd.DataFrame(rows)
    groups = {}
    for label, ids in [('points_first', points_first), ('selected', selected_idx)]:
        actual = result.iloc[ids].actual
        groups[label] = dict(candidates=result.iloc[ids].candidate.tolist(),
                             actual_total=float(actual.sum()) if actual.notna().all() else None,
                             **score_range(distribution[ids].max(axis=0),
                                           actual.max() if actual.notna().all() else None))
    return result, dict(receipt=metadata, residual_players=len(residuals), portfolios=groups)
