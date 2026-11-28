"""Matched forecast revision diagnostics. No scoring adjustment or policy fitting."""
from collections import defaultdict
from itertools import combinations
from math import isfinite
from statistics import mean

EPS = 1e-8


def valid(x):
    return type(x) in (float, int) and isfinite(x)


def summarize(rows):
    rows = list(rows)
    if not rows:
        return dict(n=0, changed=0, improved=0, worsened=0, right_direction=0,
                    baseline_mae=None, revised_mae=None, baseline_bias=None,
                    revised_bias=None, mean_revision=None)
    a = [r['baseline']-r['actual'] for r in rows]
    b = [r['revised']-r['actual'] for r in rows]
    delta = [r['revised']-r['baseline'] for r in rows]
    changed = [i for i,d in enumerate(delta) if abs(d)>EPS]
    return dict(n=len(rows), changed=len(changed),
                improved=sum(abs(b[i])<abs(a[i])-EPS for i in changed),
                worsened=sum(abs(b[i])>abs(a[i])+EPS for i in changed),
                right_direction=sum(-delta[i]*a[i]>EPS for i in changed),
                baseline_mae=mean(map(abs,a)), revised_mae=mean(map(abs,b)),
                baseline_bias=mean(a), revised_bias=mean(b), mean_revision=mean(delta))


def rank(rows, fields, group_field):
    groups = defaultdict(list)
    for r in rows:
        groups[r[group_field]].append(r)
    result = {}
    for group, records in groups.items():
        pairs = [(a,b) for a,b in combinations(records,2)
                 if abs(a['actual']-b['actual'])>EPS]
        if not pairs:
            continue
        scores = {}
        for f in fields:
            def score(a,b):
                d = a[f]-b[f]
                return .5 if abs(d)<=EPS else float(d*(a['actual']-b['actual'])>0)
            scores[f] = mean(score(a,b) for a,b in pairs)
        result[group] = dict(pairs=len(pairs), **scores)
    return result


def revision_review(rows, *, group_field, nba=False):
    """Rows are already exact contest/identity/time reconciled by caller.

    Call separately for each contest and checkpoint pair. Missing outcomes
    never become zero. NBA component comparisons require positive minutes.
    Rank summaries describe overlapping player comparisons, not win probability.
    """
    seen, matched = set(), []
    for raw in rows:
        pid = raw.get('id')
        if not isinstance(pid,str) or not pid.strip() or pid in seen:
            raise ValueError('Expected unique exact contest player IDs')
        seen.add(pid)
        if not isinstance(raw.get(group_field),str) or not raw[group_field].strip():
            raise ValueError('Missing ranking group')
        required = ['baseline','revised','actual']
        if nba:
            required += ['baseline_minutes','revised_minutes','actual_minutes']
        if not all(valid(raw.get(k)) for k in required):
            continue
        r = dict(raw)
        if nba:
            m, c, a = (r[k] for k in required[-3:])
            if not all(0<v<=60 for v in (m,c,a)):
                continue
            r['minutes_only'] = c*r['baseline']/m
            r['rate_only'] = m*r['revised']/c
            r['rate_baseline'] = r['baseline']/m
            r['rate_revised'] = r['revised']/c
            r['rate_actual'] = r['actual']/a
        matched.append(r)
    bands = {'all':lambda r:True,
             'up>=2':lambda r:r['revised']-r['baseline']>=2,
             'down>=2':lambda r:r['revised']-r['baseline']<=-2,
             'abs<2':lambda r:abs(r['revised']-r['baseline'])<2}
    fields = ['baseline','revised']
    components = {}
    if nba:
        bands.update({'minute up>=2':lambda r:r['revised_minutes']-r['baseline_minutes']>=2,
                      'minute down>=2':lambda r:r['revised_minutes']-r['baseline_minutes']<=-2})
        fields += ['minutes_only','rate_only']
        if matched:
            for label, f, actual in [('baseline_minutes','baseline_minutes','actual_minutes'),
                                      ('revised_minutes','revised_minutes','actual_minutes'),
                                      ('baseline_rate','rate_baseline','rate_actual'),
                                      ('revised_rate','rate_revised','rate_actual'),
                                      ('minutes_only','minutes_only','actual'),
                                      ('rate_only','rate_only','actual')]:
                components[label] = mean(abs(r[f]-r[actual]) for r in matched)
    groups = rank(matched,fields,group_field)
    n = sum(v['pairs'] for v in groups.values())
    return dict(excluded=len(seen)-len(matched),
                cohorts={k:summarize(r for r in matched if f(r)) for k,f in bands.items()},
                components=components, groups=groups, rank_pairs=n,
                pair_weighted={f:sum(v[f]*v['pairs'] for v in groups.values())/n if n else None for f in fields},
                equal_group={f:mean(v[f] for v in groups.values()) if groups else None for f in fields})
