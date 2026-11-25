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


PAIRED_RATE_POLICY = 'Reviewed minutes + paired independent production rate (60/40)'


def paired_rate_shadow(frame):
    """Research-only forecast: combine rates, then apply reviewed minutes once.

    Require two distinct fresh providers with their own points AND minutes.
    Reject pre-confirmation team evidence, conflicting rates and uncertain roles.
    A later timestamp is not proof that a provider incorporated injury news.
    """
    required = set(FIELDS) | {'fanduel_id', 'team', 'game', 'replay_evidence_json',
                              'replay_captured_at_utc', 'prelock_starter'}
    columns = ['fanduel_id', 'shadow_rate_fd', 'rate_source_count', 'rate_review_status']
    if not required <= set(frame):
        return pd.DataFrame(columns=columns)
    if frame.fanduel_id.isna().any() or not frame.fanduel_id.is_unique:
        raise ValueError('Paired rate forecasts require unique contest IDs.')
    if frame.empty:
        return pd.DataFrame(columns=columns)
    captures = pd.to_datetime(frame.replay_captured_at_utc, utc=True, errors='coerce', format='mixed')
    if captures.isna().any() or captures.nunique() != 1:
        return pd.DataFrame(columns=columns)
    capture = captures.iloc[0]
    team_cutoffs = {}
    invalid_teams = set()
    for row in frame.itertuples():
        key = (row.team, row.game)
        try:
            notes = json.loads(row.replay_evidence_json)
            if not isinstance(notes, list):
                raise ValueError
            for note in notes:
                if not isinstance(note, dict):
                    raise ValueError
                if note.get('official') is not True:
                    continue
                status = str(note.get('status','')).lower()
                starter = str(note.get('starter','')).lower()
                if status not in {'out','inactive','suspended','available','probable','questionable','doubtful'} and starter not in {'starter','bench'}:
                    continue
                stamp = pd.Timestamp(note['observed_at'])
                if pd.isna(stamp) or stamp.tzinfo is None or stamp > capture:
                    raise ValueError
                if stamp >= capture - pd.Timedelta(hours=6):
                    team_cutoffs[key] = max(team_cutoffs.get(key, stamp), stamp)
        except (ValueError, TypeError, KeyError, OverflowError):
            invalid_teams.add(key)
    output = []
    for row in frame.itertuples():
        result = [row.fanduel_id, None, 0, 'Unsupported or excluded']
        key = (row.team,row.game)
        if (key in invalid_teams or not all(isinstance(x,str) and x.strip() for x in key)
                or str(row.eligible).lower() != 'true'
                or str(row.injury_flag).upper() in {'O','OUT','Q','D','GTD'}
                or str(row.prelock_status).lower() in {'out','inactive','suspended','questionable','doubtful'}
                or row.minutes_method != 'prelock_independent_consensus'
                or row.blend_status != 'Minutes/status adjustment takes priority'):
            output.append(result)
            continue
        try:
            minutes, base = float(row.adjusted_minutes), float(row.adjusted_fd_points)
            if not (math.isfinite(base) and base > 0 and 0 < minutes <= 48):
                raise ValueError
            notes = json.loads(row.projection_sources_json)
            if not isinstance(notes,list) or len(notes) != float(row.projection_source_count):
                raise ValueError
            families, rates, weights = set(), [], []
            earliest = max(capture-pd.Timedelta(hours=6), team_cutoffs.get(key,capture-pd.Timedelta(hours=6)))
            for note in notes:
                family = note['family']
                if not isinstance(family,str) or not family.strip() or family in families:
                    raise ValueError
                families.add(family)
                stamp = pd.Timestamp(note['observed_at'])
                if pd.isna(stamp) or stamp.tzinfo is None or stamp > capture:
                    raise ValueError
                if note.get('paired_minutes') is None or stamp < earliest:
                    continue
                p,m,w = map(float,(note['points'],note['paired_minutes'],note['weight']))
                if not (0 < p <= 150 and 0 < m <= 48 and 0 < w <= 1 and 0 < p/m <= 5):
                    raise ValueError
                rates.append(p/m)
                weights.append(w)
            result[2] = len(rates)
            if len(rates) < 2:
                result[3] = 'Fewer than two fresh post-confirmation paired sources'
            elif (max(rates)-min(rates))*minutes >= 5:
                result[3] = 'Independent production rates disagree'
            else:
                consensus = sum(r*w for r,w in zip(rates,weights))/sum(weights)
                result[1] = .6*base + .4*consensus*minutes
                result[3] = 'Experimental paired-rate forecast'
        except (ValueError, TypeError, KeyError, OverflowError):
            pass
        output.append(result)
    return pd.DataFrame(output,columns=columns)


def compare_frozen_paired_rate(frame):
    """Same-row retrospective error comparison; never updates live projections."""
    summary = {'Policy': PAIRED_RATE_POLICY, 'Paired players': 0}
    needed = {'fanduel_id','eligible','verified_outcome','nba_source','actual_points',
              'daily_points','adjusted_fd_points'}
    if not needed <= set(frame):
        return pd.DataFrame([summary])
    candidates = paired_rate_shadow(frame)
    if candidates.empty:
        return pd.DataFrame([summary])
    eligible = frame.eligible.astype(str).str.lower().eq('true')
    played = frame.verified_outcome.eq('played') & frame.nba_source.fillna('').ne('')
    baseline = pd.to_numeric(frame.daily_points,errors='coerce').map(math.isfinite)
    summary['Eligible played with baseline'] = int((eligible & played & baseline).sum())
    paired = frame.merge(candidates,on='fanduel_id',validate='one_to_one')
    cols = ['daily_points','adjusted_fd_points','shadow_rate_fd','actual_points']
    paired[cols] = paired[cols].apply(pd.to_numeric,errors='coerce')
    paired = paired.loc[paired[cols].apply(lambda c:c.map(math.isfinite)).all(axis=1)
                        & paired.verified_outcome.eq('played') & paired.nba_source.fillna('').ne('')]
    if paired.empty:
        return pd.DataFrame([summary])
    errors = paired[cols[:3]].sub(paired.actual_points,axis=0)
    mae = errors.abs().mean()
    summary.update({'Paired players':len(paired),'DAILY MAE':mae.daily_points,
                    'Reviewed MAE':mae.adjusted_fd_points,'Shadow MAE':mae.shadow_rate_fd,
                    'MAE improvement vs reviewed':mae.adjusted_fd_points-mae.shadow_rate_fd,
                    'Shadow bias':errors.shadow_rate_fd.mean()})
    return pd.DataFrame([summary])
