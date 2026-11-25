"""Research-only total-score blend following independently corroborated minutes.

Do not multiply the independent point estimates by a second minutes adjustment.
Require agreement in points, corroborated reviewed minutes, and a same-source
points/minutes pair near reviewed minutes. This is not a validated live policy.
"""
import json
import math

import pandas as pd

FIELDS = ('projection_sources_json','projection_source_count','projection_source_spread',
          'independent_fd_points','minutes_method','adjusted_minutes','adjusted_fd_points',
          'eligible','injury_flag','prelock_status','blend_status')


def reviewed_minutes_shadow(pool):
    if not set(FIELDS) <= set(pool) or not pool.fanduel_id.is_unique:
        raise ValueError('Use a unique reviewed full pool with source provenance.')
    output = []
    for r in pool.itertuples():
        row = {'fanduel_id':r.fanduel_id,'shadow_combined_fd':None,
               'shadow_combined_status':'Unsupported or excluded'}
        if (str(r.eligible).lower() != 'true' or str(r.injury_flag).upper() in {'O','OUT','Q','D','GTD'}
                or str(r.prelock_status).lower() in {'out','inactive','suspended','questionable','doubtful'}
                or r.minutes_method != 'prelock_independent_consensus'
                or r.blend_status != 'Minutes/status adjustment takes priority'):
            output.append(row)
            continue
        try:
            base, minutes, consensus, count = map(float,(r.adjusted_fd_points,r.adjusted_minutes,
                                                          r.independent_fd_points,r.projection_source_count))
            if not all(map(math.isfinite,(base,minutes,consensus,count))) or not (base>0 and 0<minutes<=48 and count>=2):
                raise ValueError
            estimates = json.loads(r.projection_sources_json)
            if not isinstance(estimates,list) or len(estimates)!=count:
                raise ValueError
            families = {e['family'] for e in estimates}
            points = [float(e['points']) for e in estimates]
            weights = [float(e['weight']) for e in estimates]
            if (len(families)!=count or not all(families) or
                    not all(math.isfinite(p) and 0<p<=150 for p in points) or
                    not all(math.isfinite(w) and w>0 for w in weights) or max(points)-min(points)>=5):
                raise ValueError
            if not math.isclose(sum(p*w for p,w in zip(points,weights))/sum(weights),consensus,abs_tol=1e-6):
                raise ValueError
            paired = [float(e['paired_minutes']) for e in estimates if e.get('paired_minutes') is not None]
            if not paired or not all(math.isfinite(m) and 0<m<=48 and abs(m-minutes)<=2 for m in paired):
                raise ValueError
            row.update(shadow_combined_fd=.6*base+.4*consensus,
                       shadow_combined_status='Exploratory total-score blend')
        except (ValueError,TypeError,KeyError,OverflowError):
            pass
        output.append(row)
    return pd.DataFrame(output)


def compare_combined_shadow(pool, replay):
    """Evaluate frozen source evidence only, on identical verified played rows."""
    shadow = reviewed_minutes_shadow(pool)
    needed = {'fanduel_id','verified_outcome','nba_source','actual_points','daily_points','adjusted_fd_points'}
    if not needed <= set(replay) or not replay.fanduel_id.is_unique:
        raise ValueError('Use one verified full-slate replay.')
    frame = replay.merge(shadow, on='fanduel_id', validate='one_to_one')
    cols = ['actual_points','daily_points','adjusted_fd_points','shadow_combined_fd']
    frame[cols] = frame[cols].apply(pd.to_numeric, errors='coerce')
    finite = frame[cols].apply(lambda x: x.map(math.isfinite)).all(axis=1)
    paired = frame.loc[finite & frame.verified_outcome.eq('played')
                       & frame.nba_source.fillna('').ne('')].copy()
    if paired.empty:
        return pd.DataFrame()
    errors = paired[cols[1:]].sub(paired.actual_points, axis=0).abs().mean()
    return pd.DataFrame([{'Paired players':len(paired),'DAILY MAE':errors.daily_points,
        'Reviewed MAE':errors.adjusted_fd_points,'Experimental MAE':errors.shadow_combined_fd,
        'MAE improvement vs reviewed':errors.adjusted_fd_points-errors.shadow_combined_fd}])


COMBINED_POLICY = 'Reviewed minutes + independent points (60/40)'


def compare_frozen_combined(frame):
    """Chronological paired comparison using frozen provider timestamps.

    Older captures with missing provenance are unsupported, not zero forecasts.
    The caller validates full-slate capture chronology and unique contest IDs.
    """
    summary = {'Policy': COMBINED_POLICY, 'Paired players': 0}
    required = set(FIELDS) | {'fanduel_id', 'replay_captured_at_utc',
                              'daily_points', 'actual_points', 'verified_outcome', 'nba_source'}
    if not required <= set(frame):
        return pd.DataFrame([summary])
    if frame.fanduel_id.isna().any() or not frame.fanduel_id.is_unique:
        raise ValueError('Combined comparison requires unique player IDs.')
    def frozen(row):
        try:
            capture = pd.Timestamp(row.replay_captured_at_utc)
            notes = json.loads(row.projection_sources_json)
            if pd.isna(capture) or capture.tzinfo is None or not isinstance(notes, list) or not notes:
                return False
            for note in notes:
                stamp = pd.Timestamp(note['observed_at'])
                if pd.isna(stamp) or stamp.tzinfo is None or stamp > capture:
                    return False
            return True
        except (ValueError, TypeError, KeyError, OverflowError):
            return False
    eligible = frame.eligible.astype(str).str.lower().eq('true')
    played = frame.verified_outcome.eq('played') & frame.nba_source.fillna('').ne('')
    baseline = pd.to_numeric(frame.daily_points, errors='coerce').map(math.isfinite)
    summary['Eligible played with baseline'] = int((eligible & played & baseline).sum())
    if frame.empty:
        return pd.DataFrame([summary])
    supported = frame.loc[frame.apply(frozen, axis=1)].copy()
    if supported.empty:
        return pd.DataFrame([summary])
    predictions = reviewed_minutes_shadow(supported)
    paired = supported.merge(predictions, on='fanduel_id', validate='one_to_one')
    cols = ['daily_points', 'adjusted_fd_points', 'shadow_combined_fd', 'actual_points']
    paired[cols] = paired[cols].apply(pd.to_numeric, errors='coerce')
    finite = paired[cols].apply(lambda x: x.map(math.isfinite)).all(axis=1)
    paired = paired.loc[finite & paired.verified_outcome.eq('played')
                        & paired.nba_source.fillna('').ne('')]
    if paired.empty:
        return pd.DataFrame([summary])
    errors = paired[cols[:3]].sub(paired.actual_points, axis=0)
    mae = errors.abs().mean()
    summary.update({'Paired players': len(paired), 'DAILY MAE': mae.daily_points,
                    'Reviewed MAE': mae.adjusted_fd_points, 'Shadow MAE': mae.shadow_combined_fd,
                    'MAE improvement vs reviewed': mae.adjusted_fd_points-mae.shadow_combined_fd,
                    'Shadow bias': errors.shadow_combined_fd.mean()})
    return pd.DataFrame([summary])
