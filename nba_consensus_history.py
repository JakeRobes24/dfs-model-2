"""Research-only combination of independent minutes and historical production.

Fixed policies declared Nov 26, 2026. Forecast construction never reads outcomes.
The historical-rate policy is unchanged; do not silently apply this challenger
to the live optimizer. Compare all variants on the same supported rows.
"""
from collections import defaultdict
import json
import math
import numpy as np
import pandas as pd

from nba_distribution_review import bounded, timestamp
from nba_source_accuracy import MINUTE_SOURCES
from nba_shadow_research import historical_rate_shadow

POLICIES = {
    'Consensus minutes only (history-supported)': 'consensus_minutes_fd',
    'Historical rate only (consensus-supported)': 'historical_rate_fd',
    'Consensus minutes + historical rate': 'consensus_history_fd',
}
COLUMNS = ['fanduel_id', 'consensus_minutes', 'minute_families', 'history_rate',
           'history_rate_weight', *POLICIES.values()]
NEWS_STATUS = {'out','inactive','suspended','available','probable','questionable','doubtful'}

def _notes(value):
    rows = json.loads(value)
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('Invalid archived evidence')
    return rows

def forecast_consensus_history(frame):
    """Forecast from one exact frozen contest; actual fields are not used.

    Require two independent fresh minute families, max spread six minutes,
    ten to 48 projected minutes, and supported role/recent historical rate.
    Reject stale pre-news evidence across the same team/game. The existing
    historical prior is applied once, at the chosen minutes.
    """
    required = {'fanduel_id','team','game','eligible','adjusted_minutes',
                'adjusted_fd_points','daily_minutes','daily_points',
                'projection_sources_json','replay_evidence_json',
                'replay_captured_at_utc','replay_cutoff_utc',
                'replay_timing','replay_before_full_slate_tip'}
    if frame.empty or not required <= set(frame):
        return pd.DataFrame(columns=COLUMNS)
    ids = frame.fanduel_id.astype(str)
    capture = [timestamp(x) for x in frame.replay_captured_at_utc]
    tip = [timestamp(x) for x in frame.replay_cutoff_utc]
    if (not ids.is_unique or not ids.str.fullmatch(r'[0-9]{1,12}-[0-9]+').all()
            or ids.str.split('-').str[0].nunique()!=1
            or any(x is None for x in capture+tip) or len(set(capture))!=1
            or any(c>=t for c,t in zip(capture,tip))
            or not frame.replay_timing.eq('before_scheduled_tip').all()
            or not frame.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()):
        raise ValueError('Require one exact full-slate pre-tip capture')
    cutoff = capture[0]
    fresh = cutoff-pd.Timedelta(hours=6)
    team_news, invalid, notes = {}, set(), {}
    for r in frame.itertuples():
        key = (r.team,r.game)
        try:
            evidence = _notes(r.replay_evidence_json)
            notes[r.fanduel_id] = evidence
            if not all(isinstance(x,str) and x.strip() for x in key):
                raise ValueError('Invalid team/game')
            for item in evidence:
                if (item.get('official') is not True
                    or (str(item.get('status','')).lower() not in NEWS_STATUS
                        and str(item.get('starter','')).lower() not in {'starter','bench'})):
                    continue
                t = timestamp(item.get('observed_at'))
                if t is None or t>cutoff:
                    raise ValueError('Invalid official timestamp')
                team_news[key] = max(team_news.get(key,fresh),t)
        except (ValueError,TypeError,KeyError,OverflowError):
            invalid.add(key)
    history = historical_rate_shadow(frame)
    if history.empty:
        return pd.DataFrame(columns=COLUMNS)
    historical = history.set_index('fanduel_id')
    result = []
    for r in frame.itertuples():
        key = (r.team,r.game)
        if key in invalid or str(r.eligible).lower()!='true':
            continue
        m = bounded(r.adjusted_minutes,10,48)
        base = bounded(r.adjusted_fd_points,0,150)
        if (m is None or base is None or base<=0 or base/m>5
                or bounded(r.daily_minutes,10,48) is None
                or bounded(r.daily_points,0,150) is None):
            continue
        h = historical.loc[r.fanduel_id]
        if not math.isfinite(h.history_rate_fd) or not math.isfinite(h.history_rate_weight):
            continue
        earliest = max(fresh,team_news.get(key,fresh))
        estimates = defaultdict(list)
        def add(item,group,field):
            family = MINUTE_SOURCES.get(item.get('source'))
            if family is None or family!=item.get(group):
                return
            stamp = timestamp(item.get('observed_at'))
            value = bounded(item.get(field),0,48)
            if stamp is not None and earliest<=stamp<=cutoff and value is not None:
                estimates[family].append((stamp,value))
        try:
            for item in _notes(r.projection_sources_json):
                add(item,'family','paired_minutes')
            for item in notes[r.fanduel_id]:
                if item.get('official') is False:
                    add(item,'independent_group','minutes')
        except (ValueError,TypeError,KeyError,OverflowError):
            continue
        values = {}
        for family,rows in estimates.items():
            latest = max(t for t,_ in rows)
            vals = {v for t,v in rows if t==latest}
            if len(vals)==1:
                values[family] = next(iter(vals))
        if len(values)<2 or max(values.values())-min(values.values())>6:
            continue
        median = float(np.median(list(values.values())))
        if not 10<=median<=48:
            continue
        rate = float(h.history_rate_fd/m)
        result.append(dict(fanduel_id=r.fanduel_id,consensus_minutes=median,
                           minute_families=' | '.join(sorted(values)),
                           history_rate=rate,history_rate_weight=h.history_rate_weight,
                           consensus_minutes_fd=median*base/m,
                           historical_rate_fd=h.history_rate_fd,
                           consensus_history_fd=median*rate))
    return pd.DataFrame(result,columns=COLUMNS)

def compare_consensus_history(frame):
    """Paired played-player evaluation, no imputed DNPs or new scoring."""
    reports = [{'Policy':p,'Paired players':0} for p in POLICIES]
    required={'fanduel_id','eligible','verified_outcome','nba_source','actual_minutes',
              'actual_points','daily_points','adjusted_fd_points','adjusted_minutes'}
    if not required<=set(frame):
        return pd.DataFrame(reports)
    forecast=forecast_consensus_history(frame)
    if forecast.empty:
        return pd.DataFrame(reports)
    cols=['daily_points','adjusted_fd_points','actual_points','actual_minutes','adjusted_minutes']
    data=frame.merge(forecast,on='fanduel_id',validate='one_to_one')
    data[cols]=data[cols].apply(pd.to_numeric,errors='coerce')
    eligible=(frame.eligible.astype(str).str.lower().eq('true')
              & frame.verified_outcome.eq('played')
              & frame.nba_source.fillna('').astype(str).str.strip().ne(''))
    actual=pd.to_numeric(frame.actual_points,errors='coerce')
    baseline=pd.to_numeric(frame.adjusted_fd_points,errors='coerce')
    minutes=pd.to_numeric(frame.actual_minutes,errors='coerce')
    known=int((eligible & np.isfinite(actual) & np.isfinite(baseline) & minutes.between(10,60)).sum())
    data=data.loc[data.verified_outcome.eq('played') & data.nba_source.fillna('').astype(str).str.strip().ne('')
                  & data.actual_minutes.between(10,60)
                  & np.isfinite(data[cols+list(POLICIES.values())]).all(axis=1)]
    for report,(policy,col) in zip(reports,POLICIES.items()):
        report.update({'Eligible played with baseline':known,'Paired players':len(data)})
        if data.empty:
            continue
        error=data[col]-data.actual_points
        reviewed=(data.adjusted_fd_points-data.actual_points).abs()
        report.update({'DAILY MAE':(data.daily_points-data.actual_points).abs().mean(),
                       'Reviewed MAE':reviewed.mean(),'Shadow MAE':error.abs().mean(),
                       'MAE improvement vs reviewed':(reviewed-error.abs()).mean(),
                       'Shadow bias':error.mean(),
                       'Reviewed minutes MAE':(data.adjusted_minutes-data.actual_minutes).abs().mean(),
                       'Consensus minutes MAE':(data.consensus_minutes-data.actual_minutes).abs().mean()})
    return pd.DataFrame(reports)
