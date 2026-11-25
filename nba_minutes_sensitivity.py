"""One-variable sensitivity of archived NBA lineup projections, without reoptimizing."""
import csv,io

def sensitivity(pool_csv,lineup_csv,player_id,minute_range):
    pool={r['id']:r for r in csv.DictReader(io.StringIO(pool_csv))}
    lineups={}
    for r in csv.DictReader(io.StringIO(lineup_csv)):
        lineups.setdefault(r['lineup'],[]).append(r)
    target=pool[player_id]
    baseline_minutes=float(target['consensus_scenario_minutes'])
    baseline_points=float(target['consensus_scenario_fd'])
    if baseline_minutes<=0: raise ValueError('Positive baseline minutes required')
    out=[]
    for minutes in minute_range:
        if minutes<=0:raise ValueError('Minutes must be positive')
        projected=baseline_points*minutes/baseline_minutes
        totals={}
        for name,rows in lineups.items():
            total=0.0
            for r in rows:
                if r['player_id'] not in pool: raise ValueError('Unknown contest ID')
                total+=projected if r['player_id']==player_id else float(r['scenario_fd'])
            totals[name]=round(total,3)
        order=sorted(totals,key=lambda k:(-totals[k],int(k)))
        out.append({'minutes':minutes,'totals':totals,'ranked':order})
    return out
