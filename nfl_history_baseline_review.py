"""Retrospective, chronological NFL paired workload baseline comparison.

No DAILY forecast substitution. The fixed weights are exploratory and were
selected after the sample dates. Each prediction uses only four earlier games.
"""
from datetime import date
import math

WEIGHTS={"last":(0,0,0,1),"equal":(1,1,1,1),"recent":(1,2,3,4)}

def _paired_games(history, *, player_ids, team, target_day):
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
    return sorted(accepted.items())

def compare_history_baselines(history, *, player_ids, team, target_day):
    ordered=_paired_games(history,player_ids=player_ids,team=team,target_day=target_day)
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

def compare_split_workload_baselines(history, *, player_ids, team, target_day):
    """Evaluate all nine fixed combinations on the same earlier paired games.

    Volume is the weighted mean of pair carries; share is the weighted
    aggregate first-player share. This is descriptive, conditional on
    jointly recorded carries, and does not fit or select a scoring policy.
    """
    ordered=_paired_games(history,player_ids=player_ids,team=team,target_day=target_day)
    rows=[]
    for i in range(4,len(ordered)):
        day,actual=ordered[i]
        prior=ordered[i-4:i]
        counts={}
        for policy,weights in WEIGHTS.items():
            weighted=[sum(v[j]*w for (_,v),w in zip(prior,weights)) for j in range(2)]
            counts[policy]=(sum(weighted)/sum(weights),weighted[0]/sum(weighted))
        for volume_policy,(volume,_) in counts.items():
            for share_policy,(_,share) in counts.items():
                pred=[volume*share,volume*(1-share)]
                errors=[abs(p-a) for p,a in zip(pred,actual)]
                rows.append(dict(date=day.isoformat(),volume=volume_policy,share=share_policy,
                                 training_dates=[d.isoformat() for d,_ in prior],
                                 predicted_carries=pred,actual_carries=actual,
                                 carry_mae=sum(errors)/2,max_player_error=max(errors)))
    summary=[]
    for v in WEIGHTS:
        for s in WEIGHTS:
            group=[r for r in rows if r["volume"]==v and r["share"]==s]
            if group:
                summary.append(dict(volume=v,share=s,dates=len(group),
                                    mae=sum(r["carry_mae"] for r in group)/len(group),
                                    worst=max(r["max_player_error"] for r in group)))
    return dict(rows=rows,summary=summary,certified=False,
                status="Retrospective complete grid; no selection or scoring promotion")
