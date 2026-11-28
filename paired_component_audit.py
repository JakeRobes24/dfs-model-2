"""Read-only, paired opportunity/rate comparisons. No production scoring changes."""
from collections import defaultdict
from math import isfinite, sqrt
from statistics import mean

NBA_FIELDS = ("m", "p", "sm", "sp", "am", "ap")
NBA_POLICIES = (
    "reviewed", "source", "source_minutes_only", "source_rate_only",
    "half_minutes_only", "half_rate_only", "half_both",
)


def errors(values):
    values = list(values)
    if not values:
        return dict(n=0, mae=None, bias=None, rmse=None)
    return dict(n=len(values), mae=mean(abs(v) for v in values),
                bias=mean(values), rmse=sqrt(mean(v*v for v in values)))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def nba_component_diagnostic(rows):
    """Use normalized exact-ID, timestamp-reviewed played rows.
    
    m/p = reviewed minutes/FD; sm/sp = paired source minutes/FD;
    am/ap = observed minutes/FD. Missing/zero-minute rows are excluded
    consistently from every policy, not imputed. No fitted weights.
    """
    by_date, seen = defaultdict(list), set()
    excluded = 0
    for row in rows:
        key = (row.get("date"), row.get("id"))
        if not all(key) or key in seen:
            raise ValueError("Expected unique dated contest identities")
        seen.add(key)
        if (not all(_finite(row.get(k)) for k in NBA_FIELDS)
                or not all(row[k] > 0 for k in ("m", "sm", "am"))
                or not all(row[k] <= 70 for k in ("m", "sm", "am"))):
            excluded += 1
            continue
        m, p, sm, sp, am, ap = (row[k] for k in NBA_FIELDS)
        rate, sr, ar = p/m, sp/sm, ap/am
        forecasts = dict(reviewed=p, source=sp,
                         source_minutes_only=sm*rate,
                         source_rate_only=m*sr,
                         half_minutes_only=(m+sm)/2*rate,
                         half_rate_only=m*(rate+sr)/2,
                         half_both=(m+sm)/2*(rate+sr)/2)
        by_date[key[0]].append(dict(id=key[1], actual=ap,
                                    forecasts=forecasts, gap=abs(m-sm),
                                    reviewed_minutes=m-am, source_minutes=sm-am,
                                    reviewed_rate=rate-ar, source_rate=sr-ar))
    dates = {}
    for day, paired in sorted(by_date.items()):
        dates[day] = dict(
            fd={policy: errors(r["forecasts"][policy]-r["actual"] for r in paired)
                for policy in NBA_POLICIES},
            minutes={name: errors(r[name+"_minutes"] for r in paired)
                     for name in ("reviewed", "source")},
            rate={name: errors(r[name+"_rate"] for r in paired)
                  for name in ("reviewed", "source")},
            disagreement=[
                dict(minimum=lo, maximum=hi,
                     reviewed=errors(r["reviewed_minutes"] for r in paired
                                     if r["gap"] >= lo and (hi is None or r["gap"] < hi)),
                     source=errors(r["source_minutes"] for r in paired
                                   if r["gap"] >= lo and (hi is None or r["gap"] < hi)))
                for lo, hi in ((0, 3), (3, 6), (6, None))
            ])
    return dict(dates=dates, excluded=excluded)


# Gamebook reconstruction tuples: pass [att, cmp, yds, TD, INT],
# rush [att, yds, TD], receive [targets, catches, yds, TD].
# 4for4 has catches but not targets; do not invent targets from catches.
NFL_FIELDS = (
    ("pass", "pass_attempts", 0, 5),
    ("pass", "passing_yards", 2, 5),
    ("pass", "passing_td", 3, 5),
    ("pass", "interceptions", 4, 5),
    ("rush", "rushing_attempts", 0, 3),
    ("rush", "rushing_yards", 1, 3),
    ("rush", "rushing_td", 2, 3),
    ("receive", "receptions", 1, 4),
    ("receive", "receiving_yards", 2, 4),
    ("receive", "receiving_td", 3, 4),
)


def nfl_component_pairs(forecast, actual):
    """Pair an already identity/cutoff-verified provider row with gamebook data.
    
    Absent components are unknown, not zero. Reject unexpected tuple shapes.
    """
    result = {}
    for group, metric, index, length in NFL_FIELDS:
        values = actual.get(group)
        if values is None:
            continue
        if not isinstance(values, (list, tuple)) or len(values) != length:
            raise ValueError("Unexpected archived gamebook component shape")
        predicted = forecast.get(metric)
        observed = values[index]
        if _finite(predicted) and _finite(observed):
            result[metric] = (predicted, observed)
    return result


def yardage_attribution(projected_volume, actual_volume, projected_yards, actual_yards, factor):
    """Exact midpoint decomposition of yardage-points error, conditional on positive volume."""
    vals = (projected_volume, actual_volume, projected_yards, actual_yards, factor)
    if not all(_finite(v) for v in vals) or min(projected_volume, actual_volume, factor) <= 0:
        return None
    pr, ar = projected_yards/projected_volume, actual_yards/actual_volume
    return dict(volume=(projected_volume-actual_volume)*(pr+ar)/2*factor,
                rate=(pr-ar)*(projected_volume+actual_volume)/2*factor)
