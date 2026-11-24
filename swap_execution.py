"""Validate an exact-ID NBA swap and find a legal single-slot edit sequence.

A legal target is not necessarily reachable by direct replacements. Never
certify a multi-slot editor transaction unless its behavior is verified.
"""
from functools import lru_cache
from math import isfinite

SLOTS = ('PG', 'SG', 'SF', 'PF', 'C', 'G/F', 'F/C', 'UTIL', 'UTIL')
LABELS = SLOTS[:7] + ('UTIL 1', 'UTIL 2')


def plan_edits(before, after, players, closed=(), cap=60000):
    """players: ID -> {salary, slots, name, team}; closed: all started IDs.

    Return direct edits, no-change, or an explicitly unverified multi-slot
    transition. Each direct edit preserves a full legal nine-player roster.
    """
    before, after, closed = tuple(before), tuple(after), set(closed)
    def cost(pid):
        value = players[pid]['salary']
        if isinstance(value, bool) or not isfinite(value) or value < 0 or int(value) != value:
            raise ValueError('Invalid contest salary')
        return int(value)
    def total(roster):
        return sum(cost(pid) for pid in roster)
    for roster in (before, after):
        if len(roster) != 9 or len(set(roster)) != 9:
            raise ValueError('Nine unique contest IDs required')
        if any(pid not in players for pid in roster):
            raise ValueError('Unknown contest ID')
        if any(slot not in players[pid]['slots'] for slot, pid in zip(SLOTS, roster)):
            raise ValueError('Invalid slot eligibility')
        if total(roster) > cap:
            raise ValueError('Salary cap exceeded')
    changed = tuple(i for i in range(9) if before[i] != after[i])
    if any(before[i] in closed or after[i] in closed for i in changed):
        raise ValueError('Started player or slot cannot be changed')
    def details(i, budget):
        a, b = before[i], after[i]
        return {'slot': LABELS[i], 'out_id': a, 'in_id': b,
                'out_name': players[a]['name'], 'out_team': players[a]['team'],
                'out_salary': cost(a), 'in_name': players[b]['name'],
                'in_team': players[b]['team'], 'in_salary': cost(b),
                'salary_after': budget}
    @lru_cache(None)
    def search(done):
        roster = tuple(after[i] if i in done else before[i] for i in range(9))
        if len(done) == len(changed):
            return ()
        for i in sorted(set(changed)-set(done), key=lambda i: (cost(after[i])-cost(before[i]), i)):
            if after[i] in roster:
                continue
            budget = total(roster) - cost(before[i]) + cost(after[i])
            if budget > cap:
                continue
            tail = search(tuple(sorted((*done, i))))
            if tail is not None:
                return (details(i, budget), *tail)
        return None
    steps = search(())
    return {'mode': 'no_change' if not changed else 'direct' if steps is not None else 'multi_slot_unverified',
            'steps': list(steps or ()), 'changes': [details(i, None) for i in changed],
            'before_salary': total(before), 'after_salary': total(after)}


def assign_for_execution(before, target, players, closed=(), cap=60000):
    """Keep the optimized player set, but minimize legal entry edits.

    Try an equivalent slot assignment rather than force unnecessary moves.
    Started players remain fixed; only direct fully legal sequences qualify.
    """
    before, target, closed = tuple(before), tuple(target), set(closed)
    original = plan_edits(before, target, players, closed, cap)
    best = (target, original) if original['mode'] != 'multi_slot_unverified' else None
    target_set = set(target)
    choices = [tuple(sorted((p for p in target_set if slot in players[p]['slots']
                            and (p not in closed or p == before[i])),
                            key=lambda p: (p != before[i], str(p))))
               if before[i] not in closed else (before[i],)
               for i, slot in enumerate(SLOTS)]
    order = sorted(range(9), key=lambda i: (len(choices[i]), i))
    assigned = [None]*9
    def visit(depth, used, changes):
        nonlocal best
        if best is not None and changes >= len(best[1]['changes']):
            return
        if depth == 9:
            roster = tuple(assigned)
            result = plan_edits(before, roster, players, closed, cap)
            if result['mode'] != 'multi_slot_unverified':
                best = (roster, result)
            return
        i = order[depth]
        for p in choices[i]:
            if p not in used:
                assigned[i] = p
                visit(depth+1, used | {p}, changes + (p != before[i]))
    visit(0, set(), 0)
    return best if best is not None else (target, original)
