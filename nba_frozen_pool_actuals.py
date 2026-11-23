"""Audit NBA frozen projections against source-verified FanDuel final points by contest ID."""
import csv, io, math
from collections import defaultdict

def audit_frozen_pool(pool_csv, actuals_csv, lineups_csv=None):
    pool_rows=list(csv.DictReader(io.StringIO(pool_csv)))
    actual_rows=list(csv.DictReader(io.StringIO(actuals_csv)))
    if not pool_rows or not actual_rows: raise ValueError("Pool and actuals required")
    pool={}
    for p in pool_rows:
        pid=p.get("id","").strip()
        if not pid or pid in pool: raise ValueError("Duplicate or blank contest ID")
        pool[pid]=p
    actuals={}
    for a in actual_rows:
        pid=a.get("player_id","").strip()
        if not pid or pid in actuals or pid not in pool: raise ValueError("Duplicate or unknown actual ID")
        status=a.get("result_status","").strip().upper()
        if status not in ("PLAYED","DNP","MISSING"): raise ValueError("Invalid result status")
        raw=a.get("actual_fd","").strip()
        if status=="PLAYED":
            if not raw: raise ValueError("Played result missing points")
            score=float(raw)
            if not math.isfinite(score) or score<0: raise ValueError("Invalid actual score")
            if not a.get("source_url","").strip() or not a.get("verified_at_utc","").strip():
                raise ValueError("Played result requires source and timestamp")
        else:
            if raw: raise ValueError("DNP/missing result cannot be silently scored as zero")
            score=None
        actuals[pid]=(status,score)
    coverage={"pool":len(pool),"played":0,"dnp":0,"missing":0,"unreported":0}
    errors=defaultdict(list)
    paired=[]
    for pid,p in pool.items():
        if pid not in actuals:
            coverage["unreported"]+=1
            continue
        status,score=actuals[pid]
        coverage[status.lower()]+=1
        if status!="PLAYED": continue
        projected={}
        for key in ("daily_fd","consensus_scenario_fd"):
            raw=p.get(key,"").strip()
            if raw:
                value=float(raw)
                if not math.isfinite(value): raise ValueError("Nonfinite projection")
                projected[key]=value
                errors[key].append(score-value)
        if len(projected)==2:
            paired.append((score-projected["daily_fd"],score-projected["consensus_scenario_fd"]))
    def metrics(values):
        return {"n":len(values),
                "mae":round(sum(abs(v) for v in values)/len(values),4) if values else None,
                "bias_actual_minus_projected":round(sum(values)/len(values),4) if values else None}
    result={"coverage":coverage,"metrics":{k:metrics(v) for k,v in errors.items()},
            "paired":{"n":len(paired),"daily_mae":metrics([a for a,b in paired])["mae"],
                      "scenario_mae":metrics([b for a,b in paired])["mae"]},
            "complete_full_pool_actuals":coverage["unreported"]==0 and coverage["missing"]==0,
            "lineups":[]}
    if lineups_csv is not None:
        groups=defaultdict(list)
        for r in csv.DictReader(io.StringIO(lineups_csv)): groups[r["lineup"]].append(r["player_id"])
        for label,ids in sorted(groups.items(),key=lambda pair:int(pair[0])):
            if len(ids)!=9 or len(set(ids))!=9 or any(pid not in pool for pid in ids):
                raise ValueError("Invalid lineup IDs")
            outcomes=[actuals.get(pid) for pid in ids]
            complete=all(v is not None and v[0]=="PLAYED" for v in outcomes)
            result["lineups"].append({"lineup":label,
                "actual_fd":round(sum(v[1] for v in outcomes),3) if complete else None,
                "complete_nine_played":complete})
    return result
