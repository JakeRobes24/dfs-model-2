"""Historical workload regime flags; no numerical forecast or automatic override."""
from datetime import date
import math

def compare_backfield_windows(history, *, player_ids, team, target_day):
    """Compare two disjoint four-game windows using exact historical identities.

    Fixed exploratory thresholds: 10 percentage points in share, 20 percent
    in combined volume. These are review triggers, not validated model weights.
    Historical data retrieved later cannot establish a frozen pre-lock snapshot.
    """
    target=date.fromisoformat(target_day)
    if len(player_ids)!=2 or len(set(player_ids))!=2 or any(not isinstance(i,str) or not i for i in player_ids):
        raise ValueError("Two distinct explicit player IDs required")
    accepted=[]
    seen=set()
    for r in history:
        day=date.fromisoformat(r["date"])
        if day>=target or r.get("team")!=team or r.get("season_type")!="regular":
            continue
        if not isinstance(r.get("source"),str) or not r["source"].strip() or not r.get("opponent"):
            raise ValueError("Source and opponent required")
        if day in seen:
            raise ValueError("Duplicate paired game date")
        seen.add(day)
        c=r.get("carries")
        if not isinstance(c,dict) or set(c)!=set(player_ids):
            raise ValueError("Explicit counts for both players required")
        values=[c[i] for i in player_ids]
        if any(type(v) is not int or not 0<=v<=60 for v in values) or not 0<sum(values)<=60:
            raise ValueError("Invalid paired actual carries")
        accepted.append((day,*values))
    accepted.sort(reverse=True)
    result={"target_day":target_day,"team":team,"player_ids":list(player_ids),
            "games_available":len(accepted),"supported":len(accepted)>=8,"certified":False,
            "warning":"Exploratory role-review flag only; pair carries are not team volume. No scoring override or frozen capture certification."}
    if len(accepted)<8:
        return result
    def summarize(rows):
        a=sum(x[1] for x in rows)
        b=sum(x[2] for x in rows)
        return {"dates":[x[0].isoformat() for x in rows],"pair_carries_per_game":(a+b)/len(rows),
                "first_player_carries_per_game":a/len(rows),"second_player_carries_per_game":b/len(rows),
                "first_player_share":a/(a+b)}
    recent,prior=summarize(accepted[:4]),summarize(accepted[4:8])
    share=recent["first_player_share"]-prior["first_player_share"]
    volume=recent["pair_carries_per_game"]/prior["pair_carries_per_game"]-1
    result.update(recent=recent,prior=prior,share_change_pp=share*100,volume_change_pct=volume*100,
                  share_review=abs(share)>=.10,volume_review=abs(volume)>=.20)
    return result
