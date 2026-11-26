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


OFFENSE = {"QB","RB","WR","TE"}
UNAVAILABLE = {"out","inactive","suspended","ir"}


def team_workload_review(contest, records, *, team, game, cutoff_utc=None):
    """Audit full team opportunity coverage before using a team-level budget.

    Missing/invalid/late records remain unresolved. Sum only individually
    accepted records, never treat missing players as zero. Contest status is
    not independent official availability certification.
    """
    ids=[p["player_id"] for p in contest]
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate contest IDs")
    by_id={p["player_id"]:p for p in contest}
    supplied={}
    for r in records:
        pid=r.get("player_id")
        if pid not in by_id or pid in supplied:
            raise ValueError("Duplicate or noncontest projection ID")
        supplied[pid]=r
    if cutoff_utc is not None:
        cutoff=_stamp(cutoff_utc)
    expected=[p for p in contest if p["team"]==team and p["game"]==game
              and len(p["positions"])==1 and p["positions"][0] in OFFENSE]
    if not expected:
        raise ValueError("No matching team offense")
    missing, invalid, conflicts, excluded, accepted = [],[],[],[],[]
    totals=dict(pass_attempts=0.,targets=0.,carries=0.)
    for p in expected:
        pid=p["player_id"]
        r=supplied.get(pid)
        out=p["status"].lower() in UNAVAILABLE
        if out:
            excluded.append(pid)
        if r is None:
            if not out:
                missing.append(pid)
            continue
        try:
            vals={k:_number(r.get(k),0,80) for k in totals}
            if cutoff_utc is not None and (
                not r.get("source") or not r.get("source_record_id")
                or _stamp(r.get("asof_utc"))>cutoff):
                raise ValueError("Unverified record")
        except ValueError:
            if not out:
                invalid.append(pid)
            continue
        if out:
            if any(v>0 for v in vals.values()):
                conflicts.append(pid)
            continue
        accepted.append(pid)
        for k,v in vals.items():
            totals[k]+=v
    gap=totals["pass_attempts"]-totals["targets"]
    # Independent rounding across players warrants a small tolerance.
    tolerance=max(.1,.01*len(accepted))
    complete=not (missing or invalid or conflicts)
    budget_ok=complete and totals["pass_attempts"]>0 and gap>=-tolerance
    return dict(team=team,game=game,offensive_players=len(expected),
                accepted_ids=accepted,missing_ids=missing,invalid_ids=invalid,
                excluded_ids=excluded,out_workload_conflicts=conflicts,
                matched_totals=totals,attempt_minus_target_gap=gap,
                complete_numeric_coverage=complete,receiving_budget_supported=budget_ok,
                timestamp_gate_used=cutoff_utc is not None,
                status="Research coverage only; not official availability or live forecast certification")


def receiving_scenarios(contest, pair, *, team_pass_attempts, other_targets, cutoff_utc=None):
    """Explicit team passing budget, two receivers, fixed other-player targets.

    Preserve each player's catch efficiency, yards/target, TD/target and all
    nonreceiving FD. Never allocate more targets than the stated pass budget.
    The fixed 35/50/65% pair-share grid is a sensitivity, not a probability.
    """
    ids=[p["player_id"] for p in contest]
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate contest IDs")
    by_id={p["player_id"]:p for p in contest}
    if len(pair)!=2 or len({p.get("player_id") for p in pair})!=2:
        raise ValueError("Exactly two distinct receivers required")
    if any(p.get("player_id") not in by_id for p in pair):
        raise ValueError("Unknown contest player")
    matched=[by_id[p["player_id"]] for p in pair]
    if (len({(p["team"],p["game"]) for p in matched})!=1
        or any(len(p["positions"])!=1 or p["positions"][0] not in {"RB","WR","TE"}
               or p["status"].lower() in UNAVAILABLE for p in matched)):
        raise ValueError("Require eligible same-team receiving players")
    attempts=_number(team_pass_attempts,1,80)
    residual=_number(other_targets,0,80)
    base=[]
    for p in pair:
        if cutoff_utc is not None and (
            not p.get("source") or not p.get("source_record_id")
            or _stamp(p.get("asof_utc"))>_stamp(cutoff_utc)):
            raise ValueError("Unverified or post-cutoff opportunity inputs")
        t=_number(p.get("targets"),.1,40)
        rec=_number(p.get("receptions"),0,t)
        y=_number(p.get("receiving_yards"),0,500)
        td=_number(p.get("receiving_td"),0,rec)
        fd=_number(p.get("projection_fd"),0,150)
        rate=(.5*rec+.1*y+6*td)/t
        base.append((p["player_id"],t,fd,rate,rec/t))
    total=sum(x[1] for x in base)
    # Explicit budget may include unallocated attempts. Never silently
    # normalize conflicting input or transfer targets from other players.
    if total+residual>attempts+1e-8:
        raise ValueError("Baseline targets exceed explicit passing budget")
    scenarios=[]
    for factor in TOTAL_MULTIPLIERS:
        volume=attempts*factor
        if volume>80 or volume<residual:
            continue
        pair_budget=min(total*factor,volume-residual)
        for share in SHARES:
            players=[]
            for (pid,t,fd,rate,catch),s in zip(base,(share,1-share)):
                targets=pair_budget*s
                players.append(dict(player_id=pid,targets=targets,receptions=targets*catch,
                                    projection_fd=fd+(targets-t)*rate,receiving_fd_per_target=rate))
            scenarios.append(dict(pass_attempts=volume,other_targets=residual,
                                  pair_targets=pair_budget,unallocated_attempts=volume-residual-pair_budget,
                                  first_player_share=share,players=players))
    return dict(baseline_pair_targets=total,baseline_first_share=base[0][1]/total,
                scenarios=scenarios,timestamp_gate_used=cutoff_utc is not None,
                status="Sensitivity only; caller-supplied team budget not independently certified")


def compare_single_game_workload_candidates(contest, candidates, points, scenarios, *, salary_cap):
    """Compare fixed six-player rosters with fixed MVP assignments.

    Require all points for supplied candidates, exact roster slots and salary
    eligibility. Do not infer missing projections or silently change MVP.
    Reuse the exact salary validator for every baseline and scenario.
    """
    ids = [c.get("candidate_id") for c in candidates]
    if not ids or any(not isinstance(i,str) or not i.strip() for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError("Unique nonempty candidate IDs required")
    def scores(values):
        rows=[]
        for c in candidates:
            roster=c.get("roster_ids")
            mvp=c.get("mvp")
            if not isinstance(roster,list) or mvp not in roster:
                raise ValueError("Fixed roster and MVP required")
            legal=compare_mvp_assignments(contest,roster,values,salary_cap=salary_cap)
            selected=next((p for p in legal if p["mvp"]==mvp),None)
            if selected is None:
                raise ValueError("Fixed MVP assignment exceeds cap or is invalid")
            rows.append(dict(candidate_id=c["candidate_id"],mvp=mvp,salary=selected["salary"],
                             projected_fd=round(selected["projected_fd"],3)))
        return sorted(rows,key=lambda r:(-r["projected_fd"],r["candidate_id"]))
    baseline=scores(points)
    by_base={r["candidate_id"]:r["projected_fd"] for r in baseline}
    if not scenarios:
        raise ValueError("Explicit workload scenarios required")
    contest_ids={p["player_id"] for p in contest}
    seen=set()
    rows=[]
    for s in scenarios:
        sid=s.get("scenario_id")
        if not isinstance(sid,str) or not sid.strip() or sid in seen:
            raise ValueError("Unique scenario IDs required")
        seen.add(sid)
        updates=s.get("players")
        if not isinstance(updates,list) or not updates:
            raise ValueError("Explicit scenario player overrides required")
        altered=dict(points)
        used=set()
        for p in updates:
            pid=p.get("player_id")
            if pid not in contest_ids or pid in used or pid not in points:
                raise ValueError("Unknown, missing-baseline or duplicate scenario player")
            used.add(pid)
            altered[pid]=_number(p.get("projection_fd"),-30,150)
        ranking=scores(altered)
        best=ranking[0]["projected_fd"]
        for r in ranking:
            rows.append(dict(r,scenario_id=sid,baseline_fd=by_base[r["candidate_id"]],
                             delta_fd=round(r["projected_fd"]-by_base[r["candidate_id"]],3),
                             gap_to_best=round(best-r["projected_fd"],3),
                             tied_best=r["projected_fd"]==best))
    summary=[]
    for cid in ids:
        group=[r for r in rows if r["candidate_id"]==cid]
        summary.append(dict(candidate_id=cid,baseline_fd=by_base[cid],
                            min_fd=min(r["projected_fd"] for r in group),
                            max_fd=max(r["projected_fd"] for r in group),
                            worst_gap_to_best=max(r["gap_to_best"] for r in group),
                            tied_best_scenarios=sum(r["tied_best"] for r in group),
                            scenario_count=len(group)))
    return dict(baseline=baseline,scenarios=rows,summary=summary,
                status="Fixed roster and MVP sensitivity only; partial pool, not optimization or probabilities")
