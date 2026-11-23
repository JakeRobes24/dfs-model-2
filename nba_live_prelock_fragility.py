"""Pre-lock scenario-only ranking fragility for live Streamlit lineup candidates.

Uses the existing adjusted fantasy-point and minute columns. Does not replace the optimizer.
"""
import math


def rank_fragility(scored, lineups, *, minute_spread=2.0, max_players=None):
    if max_players is not None and (not isinstance(max_players, int) or max_players < 1):
        raise ValueError("max_players must be a positive integer or None")
    if minute_spread <= 0 or not math.isfinite(minute_spread):
        raise ValueError("Minute spread must be positive and finite")
    required_pool={"fanduel_id","adjusted_fd_points","adjusted_minutes"}
    required_lineups={"lineup","fanduel_id","adjusted_fd_points"}
    if not required_pool.issubset(scored.columns) or not required_lineups.issubset(lineups.columns):
        raise ValueError("Missing columns for prelock fragility audit")
    if scored.fanduel_id.duplicated().any():
        raise ValueError("Duplicate contest player IDs")
    candidates={}
    for name, group in lineups.groupby("lineup"):
        ids=list(group.fanduel_id)
        if len(ids)!=9 or len(set(ids))!=9:
            raise ValueError("Lineups require nine unique IDs")
        candidates[str(name)]=set(ids)
    if len(candidates)<2:
        return {"fragile":False,"rows":[],"reason":"At least two candidates required"}
    pool=scored.set_index("fanduel_id")
    if any(pid not in pool.index for ids in candidates.values() for pid in ids):
        raise ValueError("Candidate player absent from scored pool")
    base={}
    for name, group in lineups.groupby("lineup"):
        name=str(name)
        for r in group.itertuples():
            points=float(r.adjusted_fd_points)
            source=float(pool.loc[r.fanduel_id,"adjusted_fd_points"])
            if not math.isfinite(points) or abs(points-source)>1e-4:
                raise ValueError("Candidate and scored pool projection mismatch")
        base[name]=float(group.adjusted_fd_points.sum())
    ordered=sorted(base,key=lambda name:(-base[name],name))
    leader=ordered[0]
    exposure=set().union(*candidates.values())
    # Only player-specific differences can change relative rankings.
    exposed=[pid for pid in exposure if len({pid in ids for ids in candidates.values()})>1]
    def impact(pid):
        m=float(pool.loc[pid,"adjusted_minutes"])
        p=float(pool.loc[pid,"adjusted_fd_points"])
        return abs(p/m)*minute_spread if m>0 and math.isfinite(m) and math.isfinite(p) else 0
    # Deterministic priority when a caller explicitly limits the number examined.
    exposed.sort(key=lambda pid: (-impact(pid), str(pid)))
    results=[]
    checked = exposed if max_players is None else exposed[:max_players]
    invalid=[]
    for pid in checked:
        minutes=float(pool.loc[pid,"adjusted_minutes"])
        points=float(pool.loc[pid,"adjusted_fd_points"])
        if not all(math.isfinite(x) for x in (minutes,points)) or minutes<=0 or points<0:
            invalid.append(str(pid))
            continue
        low=max(0.1,minutes-minute_spread)
        high=minutes+minute_spread
        endpoint_winners=[]
        for m in (low,high):
            delta=points*(m/minutes-1)
            totals={name:base[name]+(delta if pid in ids else 0)
                    for name,ids in candidates.items()}
            endpoint_winners.append(sorted(totals,key=lambda n:(-totals[n],n))[0])
        if leader not in endpoint_winners or endpoint_winners[0]!=endpoint_winners[1]:
            results.append({"fanduel_id":pid,
                            "player":str(pool.loc[pid,"fanduel_name"]) if "fanduel_name" in pool else str(pid),
                            "baseline_minutes":round(minutes,2),
                            "low_minutes":round(low,2),"high_minutes":round(high,2),
                            "low_winner":endpoint_winners[0],"high_winner":endpoint_winners[1],
                            "baseline_leader":leader})
    if invalid:
        raise ValueError(f"Invalid minutes/projections for {len(invalid)} differential players; sensitivity is not complete")
    return {"fragile":bool(results),"rows":results,
            "baseline_leader":leader,"tested_differential_players":len(checked),
            "differential_players_total":len(exposed),
            "coverage_complete":len(checked)==len(exposed),
            "reason":"Linear one-player ±minutes sensitivity, not a new optimization or certified ceiling"}
