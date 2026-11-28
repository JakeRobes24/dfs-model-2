"""Bounded exposure opportunity-cost audit; no automatic portfolio selection."""
from collections import Counter
from itertools import combinations
from math import comb, isfinite


def audit_exposure(candidates, reference, *, entries, roster_size,
                   required_exposure=None, max_combinations=100000):
    """Compare previously legality-verified candidate sets at one forecast snapshot.

    Candidates contain candidate_id, player_ids, projected_fd. No actual results
    are needed or used. Required exposure is an existing user constraint, not
    an exposure recommendation. Report best means within the saved candidate
    universe, not full-pool optima or evidence of a tournament edge.
    """
    if type(entries) is not int or type(roster_size) is not int or entries < 2 or roster_size < 1:
        raise ValueError("Invalid entry or roster count")
    if type(max_combinations) is not int or max_combinations < 1:
        raise ValueError("Invalid enumeration limit")
    required = dict(required_exposure or {})
    if any(type(v) is not int or not 0 <= v <= entries for v in required.values()):
        raise ValueError("Invalid required exposure")
    index, sets = {}, set()
    for row in candidates:
        label = row["candidate_id"]
        ids = tuple(row["player_ids"])
        points = row["projected_fd"]
        if (not isinstance(label, str) or not label or label in index
                or len(ids) != roster_size or len(set(ids)) != roster_size
                or any(not isinstance(p, str) or not p for p in ids)
                or frozenset(ids) in sets or type(points) not in (int, float)
                or not isfinite(points)):
            raise ValueError("Invalid or duplicate candidate identity/projection")
        sets.add(frozenset(ids))
        index[label] = (ids, float(points))
    ref = tuple(sorted(reference))
    if len(ref) != entries or len(set(ref)) != entries or not set(ref) <= set(index):
        raise ValueError("Invalid reference portfolio")
    if comb(len(index), entries) > max_combinations:
        raise ValueError("Enumeration limit exceeded; use a bounded verified candidate set")

    def metrics(labels):
        counts = Counter(p for label in labels for p in index[label][0])
        return dict(candidates=labels,
                    projected_total=sum(index[label][1] for label in labels),
                    exposure=dict(sorted(counts.items())),
                    distinct_players=len(counts),
                    all_entry_core=sum(n == entries for n in counts.values()),
                    average_pair_overlap=sum(n*(n-1)/2 for n in counts.values())/comb(entries,2))

    def feasible(row):
        return all(row["exposure"].get(p,0)==n for p,n in required.items())

    original = metrics(ref)
    if not feasible(original):
        raise ValueError("Reference violates existing exposure requirement")
    rows = [r for labels in combinations(sorted(index),entries)
            if feasible(r:=metrics(labels))]
    rows.sort(key=lambda r:(-r["projected_total"],r["candidates"]))
    leader = rows[0]
    def compare(row):
        if row is None:
            return None
        return dict(row,
                    loss_vs_mean_leader=leader["projected_total"]-row["projected_total"],
                    loss_vs_reference=original["projected_total"]-row["projected_total"])
    frontier = {k:compare(next((r for r in rows if r["all_entry_core"]<=k),None))
                for k in range(roster_size+1)}
    challenges = {p:dict(reference_count=n,
                          alternative=compare(next((r for r in rows if r["exposure"].get(p,0)<n),None)))
                  for p,n in original["exposure"].items() if n>1}
    return dict(reference=compare(original), mean_leader=compare(leader),
                core_frontier=frontier, player_challenges=challenges,
                feasible_portfolios=len(rows),
                scope="Saved candidate mean-projection sensitivity only; no live exposure policy")
