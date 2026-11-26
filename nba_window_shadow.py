"""Frozen pre-tip history-window challengers; research only.

Same eight complete earlier played observations support every policy.
Use incumbent reviewed minutes/points as the anchor; compare fixed 20%
shrinkage, not a fitted or automatically promoted production policy.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
import math
import numpy as np
import pandas as pd
from nba_component_history import FIELDS, _day, _number, _components
from nba_distribution_review import bounded, timestamp
from slate_import import contest_player_keys, player_key

VERSION='2026-11-26-v1'
INPUTS=('shadow_hw_slate','shadow_hw_history_json')
POLICIES={
    'Reviewed minutes + 4-game historical rate (20%)':'shadow_hw_rate4',
    'Reviewed minutes + 8-game historical rate (20%)':'shadow_hw_rate8',
    'Reviewed rate + 8-game historical minutes (20%)':'shadow_hw_minutes8',
    '8-game historical minutes and rate (20%)':'shadow_hw_both8',
}
FROZEN_FIELDS=(*INPUTS,'shadow_hw_version','shadow_hw_captured_at',*POLICIES.values())

def attach_window_inputs(pool, rotations, slate):
    """Retain compact exact history for matched players, not outcome data.

    Veto conflicting name aliases and NBA IDs; do not skip incomplete
    observations or duplicate dates within the selected last-eight window.
    """
    if pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique:
        raise ValueError('Window inputs require unique contest IDs')
    if type(slate) is not date:
        raise ValueError('Expected exact slate date')
    histories=defaultdict(list)
    for raw in rotations:
        try:
            d=_day(raw['game_date'])
            if not slate-timedelta(days=30)<=d<slate:
                continue
            name=player_key(raw['player'])
            team=raw['team']
            histories[team,name].append(dict(raw,game_date=d.isoformat()))
        except (KeyError,ValueError,TypeError,AttributeError):
            continue
    keys=[contest_player_keys(r.fanduel_name,r.fanduel_id) for r in pool.itertuples()]
    counts=Counter((r.team,k) for r,aliases in zip(pool.itertuples(),keys) for k in aliases)
    encoded=[]
    for row,aliases in zip(pool.itertuples(),keys):
        if any(counts[row.team,k]>1 for k in aliases):
            encoded.append('[]')
            continue
        logs=[r for k in aliases for r in histories.get((row.team,k),[])]
        if len({str(r.get('nba_id') or '') for r in logs})!=1 or len(logs)<8:
            encoded.append('[]')
            continue
        logs=sorted(logs,key=lambda r:r['game_date'])
        latest=logs[-8:]
        # Check duplicates even if the ninth row is tied with the oldest chosen row.
        dc=Counter(r['game_date'] for r in logs)
        if any(dc[r['game_date']]!=1 for r in latest):
            encoded.append('[]')
            continue
        fields=sorted(FIELDS|{'nba_id','team','player','game','game_date','source','minutes'})
        entries=[{k:r.get(k) for k in fields} for r in latest]
        try:
            encoded.append(json.dumps(entries,allow_nan=False,separators=(',',':')))
        except (TypeError,ValueError):
            encoded.append('[]')
    return pool.assign(shadow_hw_slate=slate.isoformat(),shadow_hw_history_json=encoded)

def _row_predictions(row, slate):
    if (str(row.eligible).lower()!='true'
        or str(getattr(row,'injury_flag','')).strip().upper() in {'O','OUT','Q','D','GTD'}
        or str(getattr(row,'prelock_status','')).strip().lower() in
           {'out','inactive','suspended','questionable','doubtful'}
        or str(row.shadow_hw_slate)!=slate.isoformat()):
        return None
    m=bounded(row.adjusted_minutes,10,48)
    base=bounded(row.adjusted_fd_points,0,150)
    if m is None or base is None or base<=0 or base/m>5:
        return None
    try:
        logs=json.loads(row.shadow_hw_history_json)
        if not isinstance(logs,list) or len(logs)!=8 or not all(isinstance(r,dict) for r in logs):
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
                or row.team not in r['game'].split('@')
                or not isinstance(r.get('source'),str) or not r['source'].startswith('https://www.nba.com/game/')
                or not _number(r.get('minutes'),10,60)
                or not all(_number(r.get(k),0,150) for k in FIELDS)):
                return None
        four,eight=(_components(logs[-n:],[1]*n) for n in (4,8))
        if four is None or eight is None:
            return None
        rates=[c['opportunity']*c['efficiency']+c['peripherals'] for c in (four,eight)]
        if not all(math.isfinite(v) and 0<v<=5 for v in rates):
            return None
        adjusted_rate4=.8*base/m+.2*rates[0]
        adjusted_rate8=.8*base/m+.2*rates[1]
        adjusted_m=.8*m+.2*min(eight['minutes'],48)
        values=(m*adjusted_rate4,m*adjusted_rate8,adjusted_m*base/m,adjusted_m*adjusted_rate8)
        return values if all(math.isfinite(v) and 0<v<=150 for v in values) else None
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError):
        return None

def _capture_day(frame):
    required={'fanduel_id','team','fanduel_name','eligible','adjusted_minutes','adjusted_fd_points',
              'replay_captured_at_utc','replay_cutoff_utc','replay_timing','replay_before_full_slate_tip',*INPUTS}
    if frame.empty or not required<=set(frame):
        return None
    captures=[timestamp(v) for v in frame.replay_captured_at_utc]
    tips=[timestamp(v) for v in frame.replay_cutoff_utc]
    ids=frame.fanduel_id.astype(str)
    if (not ids.is_unique or not ids.str.fullmatch(r'[0-9]{1,12}-[0-9]+').all()
        or ids.str.split('-').str[0].nunique()!=1 or any(x is None for x in captures+tips)
        or len(set(captures))!=1 or any(c>=t for c,t in zip(captures,tips))
        or not frame.replay_timing.eq('before_scheduled_tip').all()
        or not frame.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()):
        return None
    days={t.tz_convert('America/New_York').date() for t in tips}
    if len(days)!=1:
        return None
    day=next(iter(days))
    return day if day>date(2026,11,26) else None

def freeze_history_windows(frame):
    """Freeze exact supported predictions on verified pre-tip captures only."""
    day=_capture_day(frame)
    if day is None:
        return frame.copy()
    out=frame.copy()
    values=[_row_predictions(r,day) or (None,)*len(POLICIES) for r in frame.itertuples()]
    out['shadow_hw_version']=VERSION
    out['shadow_hw_captured_at']=out.replay_captured_at_utc
    for i,col in enumerate(POLICIES.values()):
        out[col]=[v[i] for v in values]
    return out

def compare_frozen_history_windows(frame):
    """Use only frozen values; verify exact input arithmetic, not hindsight fill."""
    reports=[{'Policy':p,'Paired players':0} for p in POLICIES]
    if not {*FROZEN_FIELDS,'verified_outcome','nba_source','actual_points',
            'actual_minutes','daily_points'}<=set(frame):
        return pd.DataFrame(reports)
    day=_capture_day(frame)
    if day is None:
        return pd.DataFrame(reports)
    columns=list(POLICIES.values())
    expected=freeze_history_windows(frame)
    numeric=frame[['daily_points','adjusted_fd_points','actual_points','actual_minutes',*columns]].apply(pd.to_numeric,errors='coerce')
    baseline=(frame.eligible.astype(str).str.lower().eq('true')
              & frame.verified_outcome.eq('played') & frame.nba_source.fillna('').astype(str).str.strip().ne('')
              & numeric.actual_minutes.between(10,60)
              & np.isfinite(numeric[['daily_points','adjusted_fd_points','actual_points']]).all(axis=1))
    good=(baseline & frame.shadow_hw_version.eq(VERSION)
          & frame.shadow_hw_captured_at.map(timestamp).notna()
          & frame.shadow_hw_captured_at.map(timestamp).eq(frame.replay_captured_at_utc.map(timestamp)))
    for col in columns:
        good &= np.isfinite(numeric[col]) & np.isclose(numeric[col],pd.to_numeric(expected[col],errors='coerce'),rtol=1e-9,atol=1e-8)
    sample=numeric.loc[good]
    for report,col in zip(reports,columns):
        report.update({'Eligible played with baseline':int(baseline.sum()),'Paired players':len(sample)})
        if sample.empty:
            continue
        err=sample[col]-sample.actual_points
        incumbent=(sample.adjusted_fd_points-sample.actual_points).abs()
        report.update({'DAILY MAE':(sample.daily_points-sample.actual_points).abs().mean(),
                       'Reviewed MAE':incumbent.mean(),'Shadow MAE':err.abs().mean(),
                       'MAE improvement vs reviewed':(incumbent-err.abs()).mean(),'Shadow bias':err.mean()})
    return pd.DataFrame(reports)
