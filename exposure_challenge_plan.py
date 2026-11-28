"""Plan bounded full-pool exposure challenge scenarios without outcome data."""
from collections import Counter
from itertools import combinations


def exposure_challenge_plan(rosters, *, minimum_count=None, max_targets=9,
                            include_core_pairs=True, priority=None):
    """Return deterministic single and all-entry pair omissions for review.

    This is a plan, not an optimizer or a cap. Caller supplies verified exact
    player IDs and must apply contest constraints in every counterfactual.
    Missing scenarios must be visible to the caller.
    """
    groups = [tuple(r) for r in rosters]
    if (len(groups) < 2 or not groups[0]
            or any(len(r) != len(groups[0]) or len(set(r)) != len(r)
                   or any(not isinstance(p,str) or not p for p in r) for r in groups)
            or len({frozenset(r) for r in groups}) != len(groups)):
        raise ValueError("Distinct complete verified roster sets required")
    n = len(groups)
    threshold = max(2,n-1) if minimum_count is None else minimum_count
    if (type(threshold) is not int or not 2 <= threshold <= n
            or type(max_targets) is not int or not 1 <= max_targets <= 12):
        raise ValueError("Invalid review scope")
    counts = Counter(p for r in groups for p in r)
    priority = priority or {}
    eligible = sorted((p for p,c in counts.items() if c >= threshold),
                      key=lambda p:(-counts[p],-priority.get(p,0),p))
    targets = eligible[:max_targets]
    core = [p for p in targets if counts[p] == n]
    scenarios = [(p,) for p in targets]
    if include_core_pairs:
        scenarios.extend(combinations(core,2))
    return dict(exposure=dict(sorted(counts.items())),targets=targets,
                unreviewed_targets=eligible[max_targets:],
                scenarios=scenarios,minimum_count=threshold,
                complete_target_plan=len(eligible)<=max_targets)
