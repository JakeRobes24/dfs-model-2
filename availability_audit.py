"""Availability audit for frozen projections; no probability or live-score policy."""
from collections import Counter, defaultdict
from math import isfinite
from paired_component_audit import errors

OUTCOMES = ("played", "confirmed_nonplay", "unknown", "team")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def availability_audit(rows, forecast_fields):
    """Compare exactly matched actuals, separately for played and nonplayed.

    Callers must normalize source-specific outcome semantics; absence from a
    box or gamebook alone is unknown. Team units are never player availability
    observations. Positive projections are not probabilities of participation.
    """
    fields = tuple(forecast_fields)
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("Distinct forecast fields required")
    seen, groups = set(), defaultdict(list)
    for row in rows:
        key = tuple(row.get(k) for k in ("sport", "date", "contest", "id"))
        if not all(key) or key in seen:
            raise ValueError("Unique exact contest identities required")
        seen.add(key)
        if row.get("outcome") not in OUTCOMES:
            raise ValueError("Unknown outcome label")
        if row["outcome"] == "confirmed_nonplay" and row.get("actual") != 0:
            raise ValueError("Confirmed nonparticipation must have observed zero points")
        groups[key[:3]].append(row)
    result = {}
    for key, members in sorted(groups.items()):
        counts = Counter(r["outcome"] for r in members)
        by_status = defaultdict(Counter)
        for r in members:
            by_status[r.get("status") or "blank"][r["outcome"]] += 1
        common = [r for r in members if r["outcome"] in ("played", "confirmed_nonplay")
                  and finite(r.get("actual")) and all(finite(r.get(f)) for f in fields)]
        paired = {
            name: {f: errors(r[f]-r["actual"] for r in common
                             if name == "both" or r["outcome"] == name)
                   for f in fields}
            for name in ("played", "confirmed_nonplay", "both")
        }
        exposure = {}
        for field in fields:
            valid = [r for r in members if finite(r.get(field))]
            nonplay = [r for r in valid if r["outcome"] == "confirmed_nonplay" and r[field] > 0]
            unknown = [r for r in valid if r["outcome"] == "unknown" and r[field] > 0]
            exposure[field] = dict(
                nonplay_positive=len(nonplay),
                nonplay_positive_sum=sum(r[field] for r in nonplay),
                nonplay_ge10=[r["id"] for r in nonplay if r[field] >= 10],
                played_zero=[r["id"] for r in valid if r["outcome"] == "played" and r[field] == 0],
                unknown_positive=len(unknown),
                unknown_positive_sum=sum(r[field] for r in unknown))
        result[key] = dict(counts=dict(counts), by_status={k:dict(v) for k,v in by_status.items()},
                           paired=paired, exposure=exposure)
    return result
