"""Research-only NFL workload sensitivity using exact contest identities.

No scenario is a certified forecast or automatic workload reassignment. Preserve
projected receiving points and all unrelated production. Explicit carry totals
and shares are assumptions, never derived from outcomes in the scenario engine.
"""
import math
from datetime import datetime
from collections import Counter

SHARES = (.35, .5, .65)
TOTAL_MULTIPLIERS = (.8, 1., 1.2)


def _number(v, low, high):
    if type(v) not in (int,float) or not math.isfinite(v) or not low <= v <= high:
        raise ValueError("Invalid or missing numeric workload input")
    return float(v)


def _stamp(v):
    try:
        t = datetime.fromisoformat(v.replace("Z","+00:00"))
        if t.tzinfo is None:
            raise ValueError
        return t
    except (AttributeError, ValueError):
        raise ValueError("Timezone-aware projection and cutoff required")


def backfield_scenarios(contest, pair, *, cutoff_utc=None):
    """Two same-team RBs, varying pair carries and share, not entire team usage.

    pair records have exact player_id, projection_fd, carries, rushing_yards,
    rushing_td. Optional cutoff requires individually timestamped provenance.
    Total FD is adjusted by rushing-point change only; other points stay fixed.
    """
    ids=[p["player_id"] for p in contest]
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate contest IDs")
    by_id={p["player_id"]:p for p in contest}
    if len(pair)!=2 or len({p.get("player_id") for p in pair})!=2:
        raise ValueError("Exactly two distinct backfield players required")
    if any(p["player_id"] not in by_id for p in pair):
        raise ValueError("Unknown contest player")
    matched=[by_id[p["player_id"]] for p in pair]
    if (len({(p["team"],p["game"]) for p in matched})!=1
        or any(p["positions"]!=["RB"] or p["status"] in {"out","inactive","suspended","ir"} for p in matched)):
        raise ValueError("Require two eligible same-team RBs")
    baseline=[]
    for p in pair:
        if cutoff_utc is not None:
            if not p.get("source") or not p.get("source_record_id") or _stamp(p.get("asof_utc"))>_stamp(cutoff_utc):
                raise ValueError("Unverified or post-cutoff opportunity inputs")
        c=_number(p.get("carries"),.1,60)
        y=_number(p.get("rushing_yards"),0,500)
        td=_number(p.get("rushing_td"),0,10)
        fd=_number(p.get("projection_fd"),0,150)
        rush=.1*y+6*td
        baseline.append((p["player_id"],c,fd,rush/c))
    total=sum(x[1] for x in baseline)
    if total>60:
        raise ValueError("Pair carry total out of range")
    rows=[]
    for factor in TOTAL_MULTIPLIERS:
        for share in SHARES:
            projected=total*factor
            if projected>60:
                continue
            players=[]
            for (pid,c,fd,rate),s in zip(baseline,(share,1-share)):
                carries=projected*s
                players.append(dict(player_id=pid,carries=carries,projection_fd=fd+(carries-c)*rate,
                                    rush_fd_per_carry=rate))
            rows.append(dict(pair_carries=projected,first_player_share=share,players=players))
    return dict(baseline_pair_carries=total,baseline_first_share=baseline[0][1]/total,
                scenarios=rows,provenance_checked=cutoff_utc is not None,
                status="Sensitivity only; not a calibrated probability or live projection")


def compare_mvp_assignments(contest, roster_ids, projected_points, *, salary_cap):
    """All legal MVP assignments for one fixed roster, exact CSV salaries."""
    if type(salary_cap) is not int or salary_cap<=0:
        raise ValueError("Explicit positive contest cap required")
    ids=[p["player_id"] for p in contest]
    if len(set(ids))!=len(ids) or len(roster_ids)!=6 or len(set(roster_ids))!=6:
        raise ValueError("Require unique contest IDs and six unique roster players")
    by_id={p["player_id"]:p for p in contest}
    if any(pid not in by_id for pid in roster_ids):
        raise ValueError("Noncontest roster player")
    rows=[by_id[pid] for pid in roster_ids]
    if len({p["game"] for p in rows})!=1 or len({p["team"] for p in rows})!=2:
        raise ValueError("Require single-game roster containing both teams")
    # Do not assume generic roster eligibility or derive MVP prices.
    if any(set(p["roster_eligibility"])!={"MVP - 1.5X POINTS","ANYFLEX"}
           or p["status"] in {"out","inactive","suspended","ir"}
           or type(p.get("mvp_salary")) is not int or type(p.get("salary")) is not int
           or p["salary"]<=0 or 2*p["mvp_salary"]!=3*p["salary"] for p in rows):
        raise ValueError("Invalid single-game player, eligibility or pricing")
    points={pid:_number(projected_points.get(pid),-30,150) for pid in roster_ids}
    total=sum(p["salary"] for p in rows)
    base=sum(points.values())
    return sorted([dict(mvp=p["player_id"],salary=total+p["mvp_salary"]-p["salary"],
                        projected_fd=base+.5*points[p["player_id"]])
                   for p in rows if total+p["mvp_salary"]-p["salary"]<=salary_cap],
                  key=lambda p:(-p["projected_fd"],p["salary"],p["mvp"]))
