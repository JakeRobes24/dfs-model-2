"""Fixed-roster paired provider sensitivity; no scoring or selection changes."""
from math import isfinite
import pandas as pd
from nba_historical_field import _rosters
from nba_research_triage import paired_source_coverage


def candidate_paired_sensitivity(pool, candidates, as_of, *, team_review=None):
    """Hold one input fixed to isolate minutes and production-rate effects.

    Each source family uses its own paired estimates. Support is determined
    exclusively by pre-tip input fields, not by actual playing time or results.
    Unsupported players retain incumbent scores, with explicit coverage counts.
    This is not a confidence interval, new optimizer or validated forecast.
    """
    roster_sets=_rosters(pool,candidates,'lineup')
    if len(set(roster_sets.values()))!=len(roster_sets):
        raise ValueError('Distinct legal candidate sets required.')
    _,_,details=paired_source_coverage(pool,as_of,include_details=True)
    cutoff=pd.Timestamp(as_of)
    news={}
    if team_review is not None and not team_review.empty:
        if (not {'fanduel_id','Latest confirmation UTC'}<=set(team_review)
                or team_review.fanduel_id.isna().any()
                or not team_review.fanduel_id.is_unique
                or not team_review.fanduel_id.isin(pool.fanduel_id).all()):
            raise ValueError('Unique current contest team-review IDs required.')
        for pid,value in zip(team_review.fanduel_id,team_review['Latest confirmation UTC']):
            t=pd.Timestamp(value)
            if pd.isna(t) or t.tzinfo is None or t>cutoff:
                raise ValueError('Invalid team confirmation timestamp.')
            news[pid]=t
    needed=set().union(*roster_sets.values())
    base={}
    low={}
    forecasts={}
    for r in pool.loc[pool.fanduel_id.isin(needed)].itertuples():
        pid=r.fanduel_id
        try:
            fd=float(r.adjusted_fd_points)
            minutes=float(r.adjusted_minutes)
        except (ValueError,TypeError,OverflowError):
            fd=minutes=float('nan')
        if str(r.eligible).lower()!='true' or not isfinite(fd) or not 0<fd<=150:
            raise ValueError('Candidate is ineligible or lacks usable reviewed points.')
        base[pid]=fd
        low[pid]=float(r.salary)<5000
        if (not isfinite(minutes) or not 10<=minutes<=48 or not 0<fd/minutes<=5
                or str(getattr(r,'injury_flag','')).strip().upper() in {'O','OUT','Q','D','GTD'}
                or str(getattr(r,'prelock_status','')).strip().lower() in
                   {'out','inactive','suspended','questionable','doubtful'}):
            continue
        for family,stamp,points,m in details.get(pid,[]):
            if not 10<=m<=48 or (pid in news and stamp<news[pid]):
                continue
            rate_only=minutes*points/m
            time_only=m*fd/minutes
            if not all(isfinite(v) and 0<v<=150 for v in (rate_only,time_only,points)):
                continue
            forecasts.setdefault(family,{})[pid]=(rate_only,(fd+rate_only)/2,time_only,points)
    labels=('Rate only FD','Half rate FD','Minutes only FD','Source paired FD')
    rows=[]
    for family,source in sorted(forecasts.items()):
        for label,ids in roster_sets.items():
            ids=sorted(ids)
            supported=[pid for pid in ids if pid in source]
            total=sum(base[pid] for pid in ids)
            row={'Provider':family,'Lineup':label,'Reviewed FD':total,
                 'Supported players':len(supported),'Unchanged fallback players':len(ids)-len(supported),
                 'Salary below 5000 players':sum(low[pid] for pid in ids),
                 'Salary below 5000 supported':sum(low[pid] for pid in supported)}
            for i,name in enumerate(labels):
                value=sum(source[pid][i] if pid in source else base[pid] for pid in ids)
                row[name]=value
                row[name+' delta']=value-total
            rows.append(row)
    return pd.DataFrame(rows)
