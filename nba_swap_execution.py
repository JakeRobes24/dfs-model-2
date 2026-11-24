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
