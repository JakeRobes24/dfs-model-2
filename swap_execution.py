"""Compatibility adapter for legacy callers; one canonical swap planner."""
import pandas as pd
from nba_swap_execution import plan_direct_swaps, find_executable_layout, LABELS
from model import SLOTS as MODEL_SLOTS
SLOTS = tuple(MODEL_SLOTS)


def _pool(players):
    return pd.DataFrame([
        dict(fanduel_id=pid, fanduel_name=row['name'], team=row['team'],
             salary=row['salary'], roster_eligibility='/'.join(sorted(row['slots'])),
             eligible=row.get('eligible', True))
        for pid,row in players.items()
    ])


def _report(before, after, players, steps, cap):
    def details(i):
        a,b=before[i],after[i]
        return dict(slot=LABELS[i],out_id=a,in_id=b,
                    out_name=players[a]['name'],out_team=players[a]['team'],
                    out_salary=int(players[a]['salary']),
                    in_name=players[b]['name'],in_team=players[b]['team'],
                    in_salary=int(players[b]['salary']),salary_after=None)
    changes=[details(i) for i in range(9) if before[i]!=after[i]]
    ordered=[dict(slot=r['slot'],out_id=r['out_id'],in_id=r['in_id'],
                  out_name=r['out_player'],out_team=r['out_team'],out_salary=r['out_salary'],
                  in_name=r['in_player'],in_team=r['in_team'],in_salary=r['in_salary'],
                  salary_after=cap-r['remaining_salary']) for r in (steps or ())]
    return dict(mode='no_change' if not changes else 'direct' if steps is not None else 'multi_slot_unverified',
                steps=ordered,changes=changes,before_salary=sum(int(players[p]['salary']) for p in before),
                after_salary=sum(int(players[p]['salary']) for p in after))


def plan_edits(before, after, players, closed=(), cap=60000):
    before,after=tuple(before),tuple(after)
    steps=plan_direct_swaps(_pool(players),before,after,closed,cap)
    return _report(before,after,players,steps,cap)


def assign_for_execution(before, target, players, closed=(), cap=60000):
    before,target=tuple(before),tuple(target)
    layout,steps=find_executable_layout(_pool(players),before,target,closed,cap=cap)
    if layout is None:
        layout=target
    return layout,_report(before,layout,players,steps,cap)
