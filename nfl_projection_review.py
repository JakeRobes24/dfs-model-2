"""NFL independent projection review: suggestions only, no scoring promotion."""
from collections import defaultdict
from datetime import datetime
from statistics import median
import math
from nfl_daily_audit import game, team

def stamp(value):
    if not isinstance(value,str):
        raise ValueError("Timezone-aware source timestamp required")
    try:
        result=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if result.tzinfo is None:
        raise ValueError("Timezone-aware source timestamp required")
    return result

def nonempty(value):
    return isinstance(value,str) and bool(value.strip())

def review_nfl_projections(audit, evidence, *, cutoff_utc, slate_date, max_age_hours=24):
    """Require exact IDs, teams, games, dates, FanDuel format and provenance.

    Source families are supplied by the reviewer, not inferred to be independent.
    A family with multiple conflicting values is rejected; multiple records from
    one family never create consensus. All results remain advisory and retain
    the original DAILY score, even when a gap has corroborating evidence.
    """
    cutoff=stamp(cutoff_utc)
    if type(max_age_hours) not in (int,float) or not math.isfinite(max_age_hours) or not 0<max_age_hours<=168:
        raise ValueError("Invalid freshness window")
    if not isinstance(evidence,list):
        raise ValueError("Evidence must be a list")
    from datetime import date
    date.fromisoformat(slate_date)
    players=audit["players"]
    by_id={p["player_id"]:p for p in players}
    if len(by_id)!=len(players):
        raise ValueError("Duplicate audit player IDs")
    groups=defaultdict(lambda:defaultdict(list))
    rejected=[]
    valid=[]
    source_families=defaultdict(set)
    for i,r in enumerate(evidence):
        if not isinstance(r,dict):
            rejected.append({"row":i+1,"reason":"invalid_record"})
            continue
        pid=r.get("player_id")
        p=by_id.get(pid) if isinstance(pid,str) else None
        reason=None
        if p is None:
            reason="unknown_contest_player"
        elif (r.get("contest_id")!=audit["contest_id"] or r.get("slate_date")!=slate_date
              or team(r.get("team"))!=team(p["team"]) or game(r.get("game"))!=game(p["game"])
              or r.get("scoring")!="FanDuel"):
            reason="identity_date_or_scoring_mismatch"
        elif not all(nonempty(r.get(k)) for k in ("source","source_family","source_record_id")):
            reason="missing_provenance"
        elif r.get("source_family").strip().casefold() in {"daily","unknown","unverified"}:
            reason="unverified_independence"
        elif r.get("independence_reviewed") is not True:
            reason="unverified_independence"
        elif type(r.get("projection_fd")) not in (int,float) or not math.isfinite(r["projection_fd"]):
            reason="invalid_projection"
        else:
            try:
                published=stamp(r.get("asof_utc"))
                observed=stamp(r.get("observed_at"))
                age=(cutoff-published).total_seconds()/3600
                if not published<=observed<=cutoff or not 0<=age<=max_age_hours:
                    reason="stale_or_post_cutoff"
            except ValueError:
                reason="invalid_timestamp"
        if reason:
            rejected.append({"row":i+1,"player_id":pid,"reason":reason})
        else:
            family=r["source_family"].strip().casefold()
            source=r["source"].strip().casefold()
            source_families[source].add(family)
            valid.append((i+1,pid,family,source,r))

    # Establish source-to-family consistency across the entire submitted slate.
    # Exact duplicate submissions are harmless, but contradictory uses of one
    # record identifier quarantine that family for the affected player.
    # Never allow input order to decide which contradictory value is retained.
    tokens=defaultdict(list)
    blocked=defaultdict(set)
    for index,pid,family,source,r in valid:
        if len(source_families[source])!=1:
            blocked[pid].add(family)
            rejected.append({"row":index,"player_id":pid,"reason":"inconsistent_source_family"})
            continue
        tokens[(pid,family,r["source_record_id"].strip())].append((index,source,r))
    for (pid,family,_),records in tokens.items():
        signatures={(source,r["projection_fd"],stamp(r["asof_utc"]))
                    for _,source,r in records}
        if len(signatures)!=1:
            blocked[pid].add(family)
            for index,_,_ in records:
                rejected.append({"row":index,"player_id":pid,"reason":"conflicting_duplicate_record"})
            continue
        # Re-observing the same published estimate does not create another vote.
        # Retain earliest verified observation, with original row as tie breaker.
        first=min(records,key=lambda x:(stamp(x[2]["observed_at"]),x[0]))
        groups[pid][family].append(first[2])
        for index,_,_ in records:
            if index!=first[0]:
                rejected.append({"row":index,"player_id":pid,"reason":"duplicate_record"})
    rows=[]
    for p in players:
        pid=p["player_id"]
        family_values={}
        conflicts=set(blocked[pid])
        for family,records in groups[pid].items():
            # Conflicting same-family estimates require explicit review.
            values={r["projection_fd"] for r in records}
            if len(values)!=1:
                conflicts.add(family)
            elif family not in conflicts:
                family_values[family]=next(iter(values))
        values=list(family_values.values())
        center=median(values) if values else None
        tolerance=max(2.0,0.20*abs(center)) if center is not None else None
        agreement=len(values)>=2 and not conflicts and max(values)-min(values)<=tolerance
        accepted_records=[
            {k:record[k] for k in ("source","source_family","source_record_id","asof_utc","observed_at","projection_fd")}
            for family,records in groups[pid].items() if family in family_values
            for record in records
        ]
        baseline=p.get("projection_fd")
        unlabeled=p.get("unlabeled_fd_candidate")
        unavailable=str(p["status"]).strip().lower() in {"out","inactive","suspended","ir"}
        if unavailable:
            decision="contest_out"
        elif conflicts or len(values)>=2 and not agreement:
            decision="source_disagreement"
        elif baseline is None and agreement:
            decision="corroborated_gap_review"
        elif baseline is not None and agreement:
            decision="baseline_disagreement" if abs(center-baseline)>tolerance else "baseline_corroborated"
        elif baseline is None:
            decision="missing_requires_research"
        else:
            decision="baseline_only_or_single_source"
        rows.append({"player_id":pid,"player":p["player"],"team":p["team"],
                     "status":p["status"],"daily_fd":baseline,
                     "unlabeled_fd_candidate":unlabeled,"independent_family_count":len(values),
                     "family_scores":family_values,"conflicting_families":sorted(conflicts),
                     "accepted_source_records":accepted_records,
                     "review_consensus_fd":center if agreement and not unavailable else None,
                     "decision":decision})
    return {"contest_id":audit["contest_id"],"slate_date":slate_date,"cutoff_utc":cutoff_utc,
            "contest_sha256":audit["contest_sha256"],"daily_sha256":audit["daily_sha256"],
            "rows":rows,"rejected_evidence":sorted(rejected,key=lambda r:r["row"]),"certified":False,
            "warning":"Advisory review only. Source independence is reviewer-attested; no score replacement, status certification or lineup optimization."}
