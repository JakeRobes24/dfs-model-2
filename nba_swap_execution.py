"""Exact-ID, lock-aware direct swap planning. Does not place contest entries."""
from functools import lru_cache
from model import SLOTS, allowed_slots

LABELS = tuple(SLOTS[:7]) + ("UTIL 1", "UTIL 2")

def plan_direct_swaps(pool, before, after, closed_players=(), cap=60000):
    """Return ordered single-slot replacements, or None if no direct path exists.

    before/after are ordered IDs in PG,SG,SF,PF,C,G/F,F/C,UTIL1,UTIL2 order.
    Each intermediate roster must be legal. No assumption about clearing slots
    or moving a player who still occupies another slot in the entry.
    """
    before, after = tuple(before), tuple(after)
    if not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any():
        raise ValueError("Contest IDs must be unique and present")
    players = pool.set_index("fanduel_id").to_dict("index")
    closed = set(closed_players)
    if not closed <= players.keys():
        raise ValueError("Unknown closed player ID")
    def salary(ids):
        return sum(int(players[p]["salary"]) for p in ids)
    def legal(ids):
        return (len(ids) == len(SLOTS) and len(set(ids)) == len(SLOTS)
                and all(p in players and slot in allowed_slots(players[p]["roster_eligibility"])
                        for p, slot in zip(ids, SLOTS))
                and salary(ids) <= cap)
    if not legal(before) or not legal(after):
        raise ValueError("Invalid entry or candidate: ID, slot, uniqueness or salary")
    changed = [i for i in range(len(SLOTS)) if before[i] != after[i]]
    for i in changed:
        if before[i] in closed or after[i] in closed:
            raise ValueError("Cannot change a closed player or locked slot")
        if players[after[i]].get("eligible") != True:
            raise ValueError("Replacement is not eligible")
    @lru_cache(None)
    def search(state):
        if state == after:
            return ()
        for i in changed:
            if state[i] == after[i] or after[i] in state:
                continue
            candidate = state[:i] + (after[i],) + state[i+1:]
            if not legal(candidate):
                continue
            rest = search(candidate)
            if rest is not None:
                return (i,) + rest
        return None
    order = search(before)
    if order is None:
        return None
    steps, state = [], list(before)
    for i in order:
        old, new = state[i], after[i]
        state[i] = new
        steps.append({"slot": LABELS[i], "out_id": old, "in_id": new,
                      "out_player": players[old]["fanduel_name"],
                      "out_team": players[old]["team"],
                      "out_salary": int(players[old]["salary"]),
                      "in_player": players[new]["fanduel_name"],
                      "in_team": players[new]["team"],
                      "in_salary": int(players[new]["salary"]),
                      "remaining_salary": cap - salary(state)})
    return steps


def find_executable_layout(pool, before, after, closed_players=(), max_layouts=500):
    """Try alternative slot assignments of the SAME target IDs, preserving locks.

    Prefer retaining existing positions; never introduce an unrequested player.
    Return (final ordered IDs, steps) or (None, None). Bounded search is not
    a proof that no sequence exists beyond the searched assignments.
    """
    before, after = tuple(before), tuple(after)
    closed = set(closed_players)
    # Validate the supplied candidate first, including the original locked slots.
    # A legal target roster with a positional cycle is permitted here.
    direct = plan_direct_swaps(pool, before, after, closed)
    if not isinstance(max_layouts, int) or max_layouts < 1:
        raise ValueError("max_layouts must be positive")
    if direct == []:
        return after, direct
    target = set(after)
    lookup = pool.set_index("fanduel_id")
    choices = []
    for i, slot in enumerate(SLOTS):
        if before[i] in closed:
            choices.append([before[i]])
        else:
            possible = [p for p in after if p not in closed
                        and slot in allowed_slots(lookup.at[p, "roster_eligibility"])]
            possible.sort(key=lambda p: (p != before[i], p != after[i], str(p)))
            choices.append(possible)
    best = (after, direct) if direct is not None else (None, None)
    lower_bound = len(target - set(before))
    if direct is not None and len(direct) == lower_bound:
        return best
    tested = 0
    def visit(prefix, used):
        nonlocal tested, best
        if tested >= max_layouts or (best[1] is not None and len(best[1]) == lower_bound):
            return
        if len(prefix) == len(SLOTS):
            tested += 1
            steps = plan_direct_swaps(pool, before, prefix, closed)
            if steps is not None and (best[1] is None or len(steps) < len(best[1])):
                best = (tuple(prefix), steps)
            return
        for p in choices[len(prefix)]:
            if p not in used:
                visit(prefix + (p,), used | {p})
    visit((), set())
    return best
