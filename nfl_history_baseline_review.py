"""Retrospective, chronological NFL paired workload baseline comparison.

No DAILY forecast substitution. The fixed weights are exploratory and were
selected after the sample dates. Each prediction uses only four earlier games.
"""
from datetime import date
import math

WEIGHTS={"last":(0,0,0,1),"equal":(1,1,1,1),"recent":(1,2,3,4)}

def compare_history_baselines(history, *, player_ids, team, target_day):
    cutoff=date.fromisoformat(target_day)
    if len(player_ids)!=2 or len(set(player_ids))!=2:
        raise ValueError("Two distinct player IDs required")
    accepted={}
    for row in history:
        day=date.fromisoformat(row["date"])
        if day>=cutoff or row.get("team")!=team or row.get("season_type")!="regular":
            continue
        if day in accepted:
            raise ValueError("Duplicate paired game date")
        if not row.get("source") or not row.get("opponent"):
            raise ValueError("Missing historical source or opponent")
        counts=row.get("carries")
        if not isinstance(counts,dict) or set(counts)!=set(player_ids):
            raise ValueError("Explicit paired carries required")
        v=[counts[i] for i in player_ids]
        if any(type(x) is not int or not 0<=x<=60 for x in v) or not 0<sum(v)<=60:
            raise ValueError("Invalid paired workload")
        accepted[day]=v
    ordered=sorted(accepted.items())
    rows=[]
    for i in range(4,len(ordered)):
        day,actual=ordered[i]
        prior=ordered[i-4:i]
        for policy,weights in WEIGHTS.items():
            pred=[sum(v[j]*w for (_,v),w in zip(prior,weights))/sum(weights) for j in range(2)]
            ptotal,atotal=sum(pred),sum(actual)
            rows.append(dict(date=day.isoformat(),policy=policy,training_dates=[d.isoformat() for d,_ in prior],
                             predicted_carries=pred,actual_carries=actual,
                             carry_mae=sum(abs(p-a) for p,a in zip(pred,actual))/2,
                             volume_abs_error=abs(ptotal-atotal),
                             share_abs_error_pp=100*abs(pred[0]/ptotal-actual[0]/atotal)))
    summary=[]
    for policy in WEIGHTS:
        group=[r for r in rows if r["policy"]==policy]
        if group:
            summary.append(dict(policy=policy,dates=len(group),**{
                k:sum(r[k] for r in group)/len(group)
                for k in ("carry_mae","volume_abs_error","share_abs_error_pp")}))
    return dict(rows=rows,summary=summary,certified=False,
                status="Retrospective history-only benchmark; no DAILY comparison, probability calibration or promotion")
