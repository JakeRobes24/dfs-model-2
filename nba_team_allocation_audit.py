"""Retrospective regulation-minute allocation checks, not a live projection policy."""
from collections import defaultdict
from math import isfinite
from paired_component_audit import errors

POLICIES = ("raw", "normalized", "top_five_down", "top_five_up")


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and isfinite(x)


def allocation_candidates(rows):
    """Fixed pre-outcome hypotheses, retaining zero projections and FD/min.

    Requires complete finite forecast minutes for the team. Never uses actuals
    to construct a forecast. The five highest projected minutes are NOT
    necessarily the confirmed starters. An infeasible redistribution is skipped.
    """
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate team player identity")
    if not rows or any(not _number(r.get("m")) or not 0 <= r["m"] <= 48 for r in rows):
        return None
    positive = sorted((r for r in rows if r["m"] > 0), key=lambda r: (-r["m"], r["id"]))
    if len(positive) <= 5:
        return None
    total = sum(r["m"] for r in rows)
    top_ids = {r["id"] for r in positive[:5]}
    top_total = 240 * sum(r["m"] for r in positive[:5]) / total
    other_total = 240 - top_total
    transfer = .05 * top_total
    if other_total <= transfer:
        return None
    output = {}
    for r in rows:
        norm = 240*r["m"]/total
        top = r["id"] in top_ids
        down = norm*(.95 if top else (other_total+transfer)/other_total)
        up = norm*(1.05 if top else (other_total-transfer)/other_total)
        values = dict(raw=r["m"], normalized=norm, top_five_down=down, top_five_up=up)
        if any(not 0 <= v <= 48 for v in values.values()):
            return None
        output[r["id"]] = dict(top_five=top, minutes=values)
    return output


def regulation_allocation_audit(rows):
    """Report team budgets and identical played samples.

    Score only teams whose recorded player minutes reconcile to 240 within
    0.1 minute. This is a retrospective coverage gate, not a pre-tip signal.
    Unknown individual outcomes remain unknown and never become zero labels.
    """
    by_team, seen = defaultdict(list), set()
    for row in rows:
        key = (row.get("date"), row.get("team"), row.get("id"))
        if not all(key) or (key[0], key[2]) in seen:
            raise ValueError("Expected unique dated player IDs and team")
        seen.add((key[0], key[2]))
        by_team[key[:2]].append(row)
    reports, graded = [], defaultdict(list)
    for (day, team), members in sorted(by_team.items()):
        valid_forecast = all(_number(r.get("m")) and 0 <= r["m"] <= 48 for r in members)
        forecast_sum = sum(r["m"] for r in members if _number(r.get("m")))
        known = [r["am"] for r in members if _number(r.get("am")) and r["am"] >= 0]
        actual_sum = sum(known)
        candidates = allocation_candidates(members)
        accepted = candidates is not None and abs(actual_sum-240) <= .1
        report = dict(date=day, team=team, forecast_minutes=forecast_sum,
                      complete_forecasts=valid_forecast, known_actual_minutes=actual_sum,
                      unknown_outcomes=len(members)-len(known), scored=accepted)
        if accepted:
            top_members = [r for r in members if candidates[r["id"]]["top_five"]]
            if all(_number(r.get("am")) and r["am"] >= 0 for r in top_members):
                report["top_five_normalized_gap"] = sum(
                    candidates[r["id"]]["minutes"]["normalized"]-r["am"] for r in top_members)
            for r in members:
                if not all(_number(r.get(k)) for k in ("m","p","am","ap")) or min(r["m"], r["am"]) <= 0:
                    continue
                minutes = candidates[r["id"]]["minutes"]
                graded[day].append(dict(
                    id=r["id"], top_five=candidates[r["id"]]["top_five"],
                    minutes={k:v-r["am"] for k,v in minutes.items()},
                    fd={k:v*r["p"]/r["m"]-r["ap"] for k,v in minutes.items()}))
        reports.append(report)
    dates = {}
    for day, values in sorted(graded.items()):
        dates[day] = {metric:{k:errors(r[metric][k] for r in values) for k in POLICIES}
                      for metric in ("minutes","fd")}
        dates[day]["top_five_minutes"] = {
            label:errors(r["minutes"]["normalized"] for r in values if r["top_five"] == flag)
            for label,flag in (("top_five",True),("others",False))}
    return dict(teams=reports, dates=dates)
