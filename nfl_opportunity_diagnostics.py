"""Read-only opportunity and production diagnostics; never change scores."""
import math
from nfl_daily_audit import team, game
from nfl_workload_scenarios import team_workload_review

def finite(n):
    return type(n) in (int,float) and math.isfinite(n)

def decompose_opportunity(forecast, actual):
    """Symmetric exact decomposition of error into group volume and allocation."""
    if not isinstance(forecast,dict) or not isinstance(actual,dict) or not forecast or set(forecast)!=set(actual):
        raise ValueError("Identical nonempty opportunity IDs required")
    if any(not finite(v) or v<0 for v in [*forecast.values(),*actual.values()]):
        raise ValueError("Nonnegative explicit opportunity counts required")
    f,a=sum(forecast.values()),sum(actual.values())
    if not finite(f) or not finite(a) or f<=0 or a<=0:
        raise ValueError("Positive group totals required for share attribution")
    rows=[]
    for pid,x in forecast.items():
        y=actual[pid]
        fs,ass=x/f,y/a
        rows.append(dict(player_id=pid,forecast=x,actual=y,forecast_share=fs,actual_share=ass,
                         volume_effect=(a-f)*(fs+ass)/2,
                         allocation_effect=(ass-fs)*(a+f)/2,error=y-x))
    return dict(forecast_total=f,actual_total=a,volume_error=a-f,rows=rows,
                status="Retrospective attribution only; group scope is not automatically whole-team volume")

def audit_offensive_components(audit):
    """Check labeled passing/rushing/receiving subtotals, never replace DAILY FD.

    Omitted fumbles, conversions and other scoring events can explain residuals.
    """
    required=("passing_yards","passing_td","interceptions","rushing_attempts",
              "rushing_yards","rushing_td","receptions","targets","receiving_yards",
              "receiving_td","completions","pass_attempts")
    rows=[]
    teams={}
    seen=set()
    for p in audit["players"]:
        pid=p["player_id"]
        if pid in seen:
            raise ValueError("Duplicate contest player")
        seen.add(pid)
        if p["positions"][0] not in {"QB","RB","WR","TE"}:
            continue
        t,g=team(p["team"]),game(p["game"])
        if not t or not g:
            raise ValueError("Invalid team/game")
        teams.setdefault((t,g),[])
        c=p.get("offensive_components",{})
        base=p.get("projection_fd")
        valid=all(finite(c.get(k)) for k in required)
        if valid:
            valid=(all(c[k]>=0 for k in required if k not in {"rushing_yards","receiving_yards","passing_yards"})
                   and c["completions"]<=c["pass_attempts"] and c["receptions"]<=c["targets"])
        subtotal=None
        if valid:
            subtotal=(.04*c["passing_yards"]+4*c["passing_td"]-c["interceptions"]
                      +.1*c["rushing_yards"]+6*c["rushing_td"]
                      +.5*c["receptions"]+.1*c["receiving_yards"]+6*c["receiving_td"])
        residual=subtotal-base if subtotal is not None and finite(base) else None
        rows.append(dict(player_id=pid,player=p["player"],team=t,game=g,status=p["status"],
                         component_subtotal=subtotal,daily_fd=base,subtotal_minus_daily=residual,
                         residual_flag=residual is not None and abs(residual)>1,
                         component_fields_complete=valid))
        if valid:
            teams[t,g].append(dict(player_id=pid,pass_attempts=c["pass_attempts"],
                                   targets=c["targets"],carries=c["rushing_attempts"]))
    normalized=[{**p,"team":team(p["team"]),"game":game(p["game"])} for p in audit["players"]]
    budgets=[team_workload_review(normalized,records,team=t,game=g)
             for (t,g),records in sorted(teams.items())]
    return dict(contest_id=audit["contest_id"],contest_sha256=audit["contest_sha256"],
                daily_sha256=audit["daily_sha256"],rows=rows,team_budgets=budgets,
                certified=False,warning="Partial offensive subtotal and opportunity coverage only; no automatic scoring or official status verification.")
