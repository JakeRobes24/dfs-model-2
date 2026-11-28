"""Common-support NBA player ordering audit, never a lineup or win-probability model."""
from collections import defaultdict
from itertools import combinations
from statistics import mean
from datetime import date

from forecast_revision_audit import EPS,valid


def _sign(value):
    return 0 if abs(value)<=EPS else (1 if value>0 else -1)


def player_choice_audit(records, *, forecasts, anchor='base', top_k=10):
    """Evaluate fixed forecasts on the same already-reconciled player rows.

    Caller supplies exact contest identities, pregame forecast snapshots and
    verified actuals. Pair membership uses the unchanged anchor; actual-score
    ties are excluded. A predicted tie scores half. Salary diagnostics require
    complete valid salary data for a date. Raw-score pairs are not legal
    lineup swaps: positions, correlation, contest caps and availability may
    differ. Actual outcomes are used only for evaluation.
    """
    if (type(top_k) is not int or top_k<1 or not forecasts or
            len(set(forecasts))!=len(forecasts) or anchor not in forecasts or
            any(not isinstance(k,str) or not k or k in ('actual','id','date','salary')
                for k in forecasts)):
        raise ValueError('Unique forecast fields, anchor and positive top_k required')
    groups=defaultdict(list)
    seen=set()
    for r in records:
        day=r.get('date')
        pid=r.get('id')
        if not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day:
            raise ValueError('Exact ISO slate date required')
        if not isinstance(pid,str) or not pid.strip() or (day,pid) in seen:
            raise ValueError('Unique player ID per slate required')
        seen.add((day,pid))
        if not all(valid(r.get(k)) for k in ('actual',*forecasts)):
            raise ValueError('Common finite forecast and outcome support required')
        groups[day].append(r)
    result=[]
    for day,rows in sorted(groups.items()):
        pairs=[(a,b) for a,b in combinations(rows,2) if _sign(a['actual']-b['actual'])]
        bands={'all':pairs,'anchor_gap_le5':[(a,b) for a,b in pairs if abs(a[anchor]-b[anchor])<=5],
               'anchor_gap_le2':[(a,b) for a,b in pairs if abs(a[anchor]-b[anchor])<=2]}
        salary_ok=all(valid(r.get('salary')) and r['salary']>0 for r in rows)
        if salary_ok:
            bands['salary_gap_le500']=[(a,b) for a,b in pairs if abs(a['salary']-b['salary'])<=500]
            bands['salary_gap_le500_and_anchor_gap_le5']=[
                (a,b) for a,b in bands['salary_gap_le500'] if abs(a[anchor]-b[anchor])<=5]
        def rank(k,group,value=False):
            if not group:
                return None
            def score(a,b):
                if value:
                    # FD per $1000, same denominator per player across methods.
                    actual=1000*(a['actual']/a['salary']-b['actual']/b['salary'])
                    pred=1000*(a[k]/a['salary']-b[k]/b['salary'])
                else:
                    actual=a['actual']-b['actual']
                    pred=a[k]-b[k]
                return .5 if not _sign(pred) or not _sign(actual) else float(_sign(pred)==_sign(actual))
            return mean(score(a,b) for a,b in group)
        k=min(top_k,len(rows))
        top=lambda field:sorted(rows,key=lambda r:(-r[field],r['id']))[:k]
        ideal=top('actual')
        ideal_ids={r['id'] for r in ideal}
        for field in forecasts:
            selected=top(field)
            report=dict(date=day,policy=field,players=len(rows),top_k=k,
                        top_actual_mean=mean(r['actual'] for r in selected),
                        ideal_actual_mean=mean(r['actual'] for r in ideal),
                        top_actual_hits=sum(r['id'] in ideal_ids for r in selected))
            for name,group in bands.items():
                report[name+'_pairs']=len(group)
                report[name+'_accuracy']=rank(field,group)
            if salary_ok:
                value_top=sorted(rows,key=lambda r:(-r[field]/r['salary'],r['id']))[:k]
                report['value_accuracy_on_raw_nonties']=rank(field,pairs,value=True)
                report['top_value_actual_fd_per_1000']=mean(1000*r['actual']/r['salary'] for r in value_top)
            result.append(report)
    return result
