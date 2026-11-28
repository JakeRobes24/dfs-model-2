"""Fixed pooled history component challenger, separate from live projection.

Historical prior locked from an earlier archived cohort. No adjustment to
opaque reviewed totals, no target-game inputs, no automatic scoring changes.
"""
from collections import Counter,defaultdict
from datetime import date,timedelta
import json
import math

import numpy as np
import pandas as pd

from nba_component_history import FIELDS,_day,_number
from nba_component_pool_replay import CHANNELS,component_pool_forecast
from nba_distribution_review import bounded,timestamp
from slate_import import contest_player_keys,player_key

VERSION='2026-11-28-pooled-history-v1'
PRIOR_END=date(2026,11,17)
# Source: DFS_Model_2_NBA_Rotation_Replay.zip, 2026-11-18.json,
# SHA-256 8ec493160d935b4b4faed6efb144077f8c52fb5e2529d0b9023de1846a474e12.
# 2132 complete earlier played rows; 21 dates, 30 clubs, incomplete game coverage.
PRIOR={'minutes':53297.6666666642,'opp':24980.4,'net':22214,
       'reb':11516.4,'ast':8913.0,'stocks':8586}
INPUTS=('pooled_hw_slate','pooled_hw_history_json')
FROZEN_FIELDS=(*INPUTS,'pooled_hw_version','pooled_hw_captured_at',
               'pooled_hw_personal_fd','pooled_hw_pooled_fd',
               'pooled_hw_components_json')
POLICIES=('Personal four-game components at reviewed minutes',
          'Pooled net/assist/stocks at reviewed minutes')


def attach_pooled_history(pool, rotations, slate):
    """Retain the most recent four observed same-team records, no gap filling."""
    if type(slate) is not date or pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique:
        raise ValueError('Exact slate date and unique contest IDs required')
    groups=defaultdict(list)
    for raw in rotations:
        try:
            day=_day(raw['game_date'])
            if slate-timedelta(days=30)<=day<slate:
                groups[raw['team'],player_key(raw['player'])].append(dict(raw,game_date=day.isoformat()))
        except (KeyError,ValueError,TypeError,AttributeError):
            continue
    aliases=[contest_player_keys(r.fanduel_name,r.fanduel_id) for r in pool.itertuples()]
    counts=Counter((r.team,k) for r,keys in zip(pool.itertuples(),aliases) for k in keys)
    encoded=[]
    for r,keys in zip(pool.itertuples(),aliases):
        logs=[x for k in keys for x in groups.get((r.team,k),[])]
        if any(counts[r.team,k]>1 for k in keys) or len(logs)<4 or len({str(x.get('nba_id') or '') for x in logs})!=1:
            encoded.append('[]')
            continue
        latest=sorted(logs,key=lambda x:x['game_date'])[-4:]
        days=Counter(x['game_date'] for x in logs)
        if any(days[x['game_date']]!=1 for x in latest):
            encoded.append('[]')
            continue
        fields=sorted(FIELDS|{'nba_id','team','player','game','game_date','source','minutes'})
        try:
            encoded.append(json.dumps([{k:x.get(k) for k in fields} for x in latest],
                                      sort_keys=True,allow_nan=False,separators=(',',':')))
        except (TypeError,ValueError):
            encoded.append('[]')
    return pool.assign(pooled_hw_slate=slate.isoformat(),pooled_hw_history_json=encoded)


def pooled_prediction(row,slate):
    if (slate<=PRIOR_END or str(row.pooled_hw_slate)!=slate.isoformat()
            or str(row.eligible).lower()!='true'
            or str(getattr(row,'injury_flag','')).strip().upper() in {'O','OUT','Q','D','GTD'}
            or str(getattr(row,'prelock_status','')).strip().lower() in
               {'out','inactive','suspended','questionable','doubtful'}):
        return None
    m=bounded(row.adjusted_minutes,10,48)
    if m is None:
        return None
    try:
        logs=json.loads(row.pooled_hw_history_json)
        if not isinstance(logs,list) or len(logs)!=4 or not all(isinstance(r,dict) for r in logs):
            return None
        ids={str(r.get('nba_id') or '') for r in logs}
        dates=[_day(r['game_date']) for r in logs]
        aliases=contest_player_keys(row.fanduel_name,row.fanduel_id)
        if (len(ids)!=1 or not next(iter(ids)).isdigit() or dates!=sorted(set(dates))
                or any(not slate-timedelta(days=30)<=d<slate for d in dates)):
            return None
        for r in logs:
            if (r.get('team')!=row.team or player_key(r.get('player','')) not in aliases
                or not isinstance(r.get('game'),str) or len(r['game'].split('@'))!=2
                or len(set(r['game'].split('@')))!=2 or row.team not in r['game'].split('@')
                or not isinstance(r.get('source'),str) or not r['source'].startswith('https://www.nba.com/game/')
                or not _number(r.get('minutes'),10,60) or not all(_number(r.get(k),0,150) for k in FIELDS)):
                return None
        values=component_pool_forecast(logs,PRIOR)
        if values is None:
            return None
        personal,pooled,history_minutes=values
        # Rebounding stays personal. Same projected playing time in both
        # alternatives, no addition to current model total.
        pooled=dict(pooled,reb=personal['reb'])
        personal={k:personal[k]*m/history_minutes for k in CHANNELS}
        pooled={k:pooled[k]*m/history_minutes for k in CHANNELS}
        a,b=sum(personal.values()),sum(pooled.values())
        if not all(math.isfinite(v) and 0<v<=150 for v in (a,b)):
            return None
        return a,b,json.dumps({'personal':personal,'pooled':pooled},sort_keys=True,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError):
        return None


def freeze_pooled_history(frame):
    from nba_window_shadow import _capture_day
    required=set(INPUTS)|{'fanduel_id','team','fanduel_name','eligible','adjusted_minutes',
                          'replay_contest_sha256','replay_daily_sha256'}
    out=frame.copy()
    if not required<=set(frame):
        return out
    # Reuse the shared exact pre-tip chronology gate with the new input names.
    day=_capture_day(frame.assign(shadow_hw_slate=frame.pooled_hw_slate,
                                 shadow_hw_history_json=frame.pooled_hw_history_json))
    if day is None or day<date(2026,11,28) or any(
            frame[k].nunique()!=1 or not frame[k].astype(str).str.fullmatch('[0-9a-f]{64}').all()
            for k in ('replay_contest_sha256','replay_daily_sha256')):
        return out
    values=[pooled_prediction(r,day) or (None,None,None) for r in frame.itertuples()]
    out['pooled_hw_version']=VERSION
    out['pooled_hw_captured_at']=out.replay_captured_at_utc
    for i,k in enumerate(FROZEN_FIELDS[-3:]):
        out[k]=[v[i] for v in values]
    return out


def compare_frozen_pooled_history(frame):
    reports=[{'Policy':p,'Paired players':0} for p in POLICIES]
    if not {*FROZEN_FIELDS,'daily_points','adjusted_fd_points','actual_points','actual_minutes',
            'eligible','verified_outcome','nba_source'}<=set(frame):
        return pd.DataFrame(reports)
    expected=freeze_pooled_history(frame.drop(columns=list(FROZEN_FIELDS[2:])))
    if not set(FROZEN_FIELDS)<=set(expected):
        return pd.DataFrame(reports)
    cols=['pooled_hw_personal_fd','pooled_hw_pooled_fd']
    numeric=frame[['daily_points','adjusted_fd_points','actual_points','actual_minutes',*cols]].apply(pd.to_numeric,errors='coerce')
    base=(frame.eligible.astype(str).str.lower().eq('true') & frame.verified_outcome.eq('played')
          & frame.nba_source.fillna('').astype(str).str.strip().ne('')
          & numeric.actual_minutes.between(10,60)
          & np.isfinite(numeric[['daily_points','adjusted_fd_points','actual_points']]).all(axis=1))
    good=(base & frame.pooled_hw_version.eq(VERSION)
          & frame.pooled_hw_captured_at.map(timestamp).notna()
          & frame.pooled_hw_captured_at.map(timestamp).eq(frame.replay_captured_at_utc.map(timestamp))
          & frame.pooled_hw_components_json.eq(expected.pooled_hw_components_json))
    for col in cols:
        good &= np.isfinite(numeric[col]) & np.isclose(numeric[col],pd.to_numeric(expected[col],errors='coerce'),rtol=1e-9,atol=1e-8)
    for report,col in zip(reports,cols):
        report.update({'Eligible played with baseline':int(base.sum()),'Paired players':int(good.sum())})
        if good.any():
            actual=numeric.loc[good,'actual_points']
            error=numeric.loc[good,col]-actual
            before=(numeric.loc[good,'adjusted_fd_points']-actual).abs()
            report.update({'DAILY MAE':(numeric.loc[good,'daily_points']-actual).abs().mean(),
                           'Reviewed MAE':before.mean(),'Shadow MAE':error.abs().mean(),
                           'MAE improvement vs reviewed':(before-error.abs()).mean(),'Shadow bias':error.mean()})
    return pd.DataFrame(reports)
