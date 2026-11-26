"""Exploratory NBA game-level residual dependence diagnostics, no score changes."""
from itertools import combinations
import math
import re
from datetime import date
import pandas as pd
from nba_distribution_review import timestamp

MIN_DATES=5
MIN_GAMES=20

def game_residual_review(frame, *, target_day):
    """Use one timestamped contest capture per earlier date.

    Compare residual cross-products within a game after date centering. This
    is descriptive covariance evidence, not a fitted correlation matrix.
    Each game receives equal weight, not each potentially overlapping pair.
    Missing outcomes are excluded, never set to zero. Conditional on playing.
    """
    fields={"slate_date","fanduel_id","team","game","eligible","verified_outcome",
            "nba_source","actual_minutes","actual_points","adjusted_minutes",
            "adjusted_fd_points","replay_captured_at_utc","replay_cutoff_utc",
            "replay_before_full_slate_tip","replay_timing"}
    if not fields<=set(frame):
        raise ValueError("Frozen game replay fields required")
    target=date.fromisoformat(target_day)
    rows=[]
    rejected=[]
    accepted_dates=[]
    def number(v):
        try:
            x=float(v)
            return x if math.isfinite(x) else None
        except (ValueError,TypeError,OverflowError):
            return None
    for label,day in frame.groupby("slate_date",sort=True,dropna=False):
        try:
            dt=date.fromisoformat(str(label))
        except ValueError:
            rejected.append({"date":str(label),"reason":"invalid_date"})
            continue
        if dt>=target:
            rejected.append({"date":str(label),"reason":"not_earlier_than_target"})
            continue
        ids=day.fanduel_id.astype(str)
        capture=[timestamp(v) for v in day.replay_captured_at_utc]
        cutoff=[timestamp(v) for v in day.replay_cutoff_utc]
        if (not ids.is_unique or not ids.str.fullmatch(r"[0-9]+-[0-9]+").all()
            or ids.str.split("-").str[0].nunique()!=1 or len(set(capture))!=1
            or any(a is None or b is None or a>=b or b.tz_convert("America/New_York").date()!=dt
                   for a,b in zip(capture,cutoff))
            or not day.replay_before_full_slate_tip.astype(str).str.lower().eq("true").all()
            or not day.replay_timing.eq("before_scheduled_tip").all()):
            rejected.append({"date":str(label),"reason":"unverified_or_ambiguous_capture"})
            continue
        clean=[]
        for r in day.to_dict("records"):
            if (str(r["eligible"]).lower()!="true" or r["verified_outcome"]!="played"
                or not isinstance(r["nba_source"],str) or not r["nba_source"].strip()):
                continue
            m,am,fp,ap=(number(r[k]) for k in ("adjusted_minutes","actual_minutes","adjusted_fd_points","actual_points"))
            if None in (m,am,fp,ap) or not (10<=m<=48 and 10<=am<=60 and fp>0):
                continue
            parts=str(r["game"]).split("@")
            if len(parts)!=2 or parts[0]==parts[1] or not all(re.fullmatch(r"[A-Z]{2,3}",p) for p in parts) or r["team"] not in parts:
                continue
            clean.append(dict(game=r["game"],team=r["team"],id=r["fanduel_id"],residual=ap-fp))
        if not clean:
            rejected.append({"date":str(label),"reason":"no_supported_played_rows"})
            continue
        # Subtract the date's mean residual, not a fitted game mean. Centering
        # within games would erase the very shared game effect being measured.
        mean=sum(r["residual"] for r in clean)/len(clean)
        for r in clean:
            r["centered"]=r["residual"]-mean
        games={}
        for r in clean:
            games.setdefault(r["game"],[]).append(r)
        for g,players in sorted(games.items()):
            same=[]
            opposite=[]
            for a,b in combinations(players,2):
                (same if a["team"]==b["team"] else opposite).append(a["centered"]*b["centered"])
            if not same or not opposite:
                continue
            rows.append(dict(slate_date=str(label),game=g,players=len(players),
                             teammate_pairs=len(same),opponent_pairs=len(opposite),
                             teammate_cross_product=sum(same)/len(same),
                             opponent_cross_product=sum(opposite)/len(opposite),
                             mean_raw_residual=sum(r["residual"] for r in players)/len(players)))
        accepted_dates.append({"date":str(label),"supported_players":len(clean),"date_mean_residual":mean})
    detail=pd.DataFrame(rows)
    dates=detail.slate_date.nunique() if len(detail) else 0
    games=len(detail)
    summary={"dates":int(dates),"games":games,"accepted_dates":accepted_dates,"rejected_dates":rejected,
             "equal_game_teammate_cross_product":float(detail.teammate_cross_product.mean()) if games else None,
             "equal_game_opponent_cross_product":float(detail.opponent_cross_product.mean()) if games else None,
             "status":"Insufficient descriptive coverage" if dates<MIN_DATES or games<MIN_GAMES else "Needs independent prospective validation",
             "certified":False,
             "warning":"Date-centered cross-products in FD points squared, not correlation coefficients or calibrated simulation parameters. No automatic promotion."}
    return detail,summary
