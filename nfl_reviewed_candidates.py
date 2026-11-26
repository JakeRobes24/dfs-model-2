"""Isolated full-pool NFL fixed-candidate review, not a lineup optimizer."""
from datetime import date
import math
from nfl_daily_audit import audit_nfl_daily, team, game
from nfl_projection_review import stamp, nonempty, review_nfl_projections
from nfl_pool_adapter import build_nfl_snapshot
from nfl_prelock_challenger import compare_prelock_candidates
from nfl_workload_scenarios import compare_mvp_assignments

def compare_reviewed_nfl(contest_raw,daily_raw,*,contest_id,single_game,slate_date,
                         cutoff_utc,daily_capture,evidence,candidates,salary_cap):
    """Rank fixed rosters only after every eligible player has a reviewed score.

    Capture provenance is caller-attested, not authenticated by this tool.
    Header-labeled DAILY scores stay unchanged. Missing scores require two
    reviewed independent families; unresolved source conflicts block ranking.
    This is a research-only comparison, not an official availability check,
    contest-rule certification, optimizer or live release.
    """
    date.fromisoformat(slate_date)
    cutoff=stamp(cutoff_utc)
    if type(salary_cap) is not int or salary_cap<=0:
        raise ValueError("Explicit positive contest salary cap required")
    audit=audit_nfl_daily(contest_raw,daily_raw,contest_id=contest_id,single_game=single_game)
    if not isinstance(daily_capture,dict) or daily_capture.get("daily_sha256")!=audit["daily_sha256"]:
        raise ValueError("DAILY capture must reference exact uploaded bytes")
    if daily_capture.get("slate_date")!=slate_date or daily_capture.get("contest_id")!=str(contest_id):
        raise ValueError("DAILY capture identity mismatch")
    if not nonempty(daily_capture.get("source_record_id")) or daily_capture.get("reviewed") is not True:
        raise ValueError("Explicit reviewed capture provenance required")
    observed=stamp(daily_capture.get("observed_at"))
    if not 0<=(cutoff-observed).total_seconds()<=24*3600:
        raise ValueError("DAILY capture stale or post-cutoff")
    review=review_nfl_projections(audit,evidence,cutoff_utc=cutoff_utc,slate_date=slate_date)
    by_id={r["player_id"]:r for r in review["rows"]}
    accepted=[]
    unresolved=[]
    excluded=[]
    for p in audit["players"]:
        pid=p["player_id"]
        if p["status"]=="out":
            excluded.append(pid)
            continue
        r=by_id[pid]
        score=p["projection_fd"]
        origin="DAILY"
        if r["decision"] in {"source_disagreement","baseline_disagreement"}:
            unresolved.append({"player_id":pid,"player":p["player"],"reason":r["decision"]})
            continue
        if score is None and r["decision"]=="corroborated_gap_review":
            score=r["review_consensus_fd"]
            origin="experimental_independent_consensus"
        if type(score) not in (int,float) or not math.isfinite(score):
            unresolved.append({"player_id":pid,"player":p["player"],"reason":"missing_reviewed_score"})
            continue
        accepted.append({**p,"projection_fd":score,"score_origin":origin,
                         "slate_date":slate_date,"asof_utc":cutoff_utc})
    report={"contest_id":str(contest_id),"slate_date":slate_date,"cutoff_utc":cutoff_utc,
            "contest_sha256":audit["contest_sha256"],"daily_sha256":audit["daily_sha256"],
            "daily_capture":daily_capture,"source_review":review,"salary_cap":salary_cap,
            "eligible_players":audit["eligible_players"],"accepted_players":accepted,
            "excluded_out_ids":excluded,"unresolved":unresolved,"rankings":[],
            "ready":False,"certified":False,
            "warning":"Experimental fixed-roster comparison only. No official status certification, full contest-rule certification or live recommendation."}
    if unresolved or not accepted:
        return report
    if not isinstance(candidates,list) or not candidates or any(not isinstance(c,dict) for c in candidates):
        raise ValueError("Supply at least one fixed candidate")
    ids=[c.get("candidate_id") for c in candidates]
    if any(not nonempty(i) for i in ids) or len(set(ids))!=len(ids):
        raise ValueError("Unique nonempty candidate IDs required")
    for c in candidates:
        if c.get("contest_id")!=str(contest_id) or c.get("slate_date")!=slate_date:
            raise ValueError("Candidate contest/date mismatch")
        if stamp(c.get("created_utc"))>cutoff:
            raise ValueError("Post-cutoff candidate")
    if single_game:
        points={p["player_id"]:p["projection_fd"] for p in accepted}
        for c in candidates:
            roster=c.get("roster_ids")
            if not isinstance(roster,list) or c.get("mvp") not in roster:
                raise ValueError("Fixed six-player roster and MVP required")
            options=compare_mvp_assignments(accepted,roster,points,salary_cap=salary_cap)
            selected=next((o for o in options if o["mvp"]==c["mvp"]),None)
            if selected is None:
                raise ValueError("Fixed MVP assignment invalid or over cap")
            report["rankings"].append({"candidate_id":c["candidate_id"],**selected})
        report["rankings"].sort(key=lambda r:(-r["projected_fd"],r["candidate_id"]))
    else:
        snapshot=build_nfl_snapshot(accepted,contest_id=str(contest_id),slate_date=slate_date,
                                    source_version="experimental-reviewed",cutoff_utc=cutoff_utc,
                                    salary_cap=salary_cap,
                                    expected_player_ids=[p["player_id"] for p in audit["players"] if p["status"]!="out"])
        report["rankings"]=compare_prelock_candidates(snapshot,candidates)
    report["ready"]=True
    return report
