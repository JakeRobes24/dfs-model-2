"""Freeze exploratory research features and compare fixed shadow forecasts.

No policy here changes a live score, lineup, or learned parameter. Evaluate on
identical eligible played-player samples, excluding unsupported features.
"""
import numpy as np
import pandas as pd

FEATURES = (
    'shadow_recent_fppm', 'shadow_recent_games', 'shadow_recent_minutes',
    'shadow_role_fppm', 'shadow_role_games', 'shadow_role_minutes',
    'shadow_absence_fppm', 'shadow_absence_games', 'shadow_absence_minutes',
    'shadow_absence_teammate', 'shadow_team_pace', 'shadow_matchup_pace',
    'shadow_team_games', 'shadow_opponent_games', 'shadow_opponent_def_rating',
    'shadow_rate_sources', 'shadow_team_sources', 'shadow_opponent_sources',
)
POLICIES = ('Recent rate', 'Confirmed role rate', 'Single OUT teammate rate', 'Pace', 'Recent rate + pace')
# Optional for backwards compatibility: old captures must retain their
# existing policy evaluations without inventing these newly frozen inputs.
OPPORTUNITY_FEATURES = (
    'shadow_single_absence_role', 'shadow_single_absence_teammate',
    'shadow_single_absence_games', 'shadow_single_absence_minutes_gap',
    'shadow_single_absence_fppm', 'shadow_single_absence_fd_games',
    'shadow_single_absence_fd_minutes', 'shadow_single_absence_sources',
)
COMPONENT_STATS = ('points','rebounds','assists','steals','blocks','turnovers',
                   'fieldGoalsAttempted','freeThrowsAttempted')
COMPONENT_FIELDS = tuple(f'component_{prefix}_{key}'
                         for prefix in ('recent','starter','bench')
                         for key in ('games','minutes','opportunities_per_minute',
                                     'net_per_opportunity','peripheral_per_minute'))
COMPONENT_POLICY = 'Component opportunity and efficiency rate (20%)'
OPPORTUNITY_POLICIES = ('Single absence + confirmed role minutes',
                        'Single absence + confirmed role rate')


def freeze_research_features(pool, summaries, splits, matchup):
    """Attach full-pool pre-slate evidence without modifying reviewed scores."""
    out = pool.copy()
    if not out.fanduel_id.is_unique:
        raise ValueError('Research capture requires unique player IDs.')
    for field in (*FEATURES, *OPPORTUNITY_FEATURES, *COMPONENT_FIELDS):
        out[field] = None
    if not summaries.empty:
        if not summaries.fanduel_id.is_unique:
            raise ValueError('Historical summary requires unique player IDs.')
        s = summaries.set_index('fanduel_id')
        for target, source in {
            'shadow_recent_fppm': 'FD points per minute',
            'shadow_recent_games': 'Games with complete FD stats',
            'shadow_recent_minutes': 'Minutes with complete FD stats',
            'shadow_rate_sources': 'Box-score sources',
        }.items():
            out[target] = out.fanduel_id.map(s[source])
        for field in COMPONENT_FIELDS:
            if field in s:
                out[field] = out.fanduel_id.map(s[field])
        for role, label in [('starter', 'Starter'), ('bench', 'Bench')]:
            mask = out.prelock_starter.eq(role)
            for target, source in {
                'shadow_role_fppm': 'FD/min as starter' if role == 'starter' else 'FD/min off bench',
                'shadow_role_games': f'{label} complete FD games',
                'shadow_role_minutes': f'{label} complete FD minutes',
            }.items():
                out.loc[mask, target] = out.loc[mask, 'fanduel_id'].map(s[source])
    if not splits.empty:
        # Do not sum effects or select the largest apparent historical gain.
        unique = splits.loc[~splits.fanduel_id.duplicated(keep=False)]
        unique = unique.loc[unique['FD rate evidence'].eq('Observed comparison')].set_index('fanduel_id')
        for target, source in {
            'shadow_absence_fppm': 'FD/min without',
            'shadow_absence_games': 'Complete FD games without',
            'shadow_absence_minutes': 'Complete FD minutes without',
            'shadow_absence_teammate': 'Out teammate',
        }.items():
            out[target] = out.fanduel_id.map(unique[source])
    mapping = {
        'shadow_single_absence_role': 'Current confirmed role',
        'shadow_single_absence_teammate': 'Out teammate',
        'shadow_single_absence_games': 'Current role games per side',
        'shadow_single_absence_minutes_gap': 'Current role minutes gap (shrunk)',
        'shadow_single_absence_fppm': 'Current role FD/min without',
        'shadow_single_absence_fd_games': 'Current role complete FD games per side',
        'shadow_single_absence_fd_minutes': 'Current role complete FD minutes per side',
        'shadow_single_absence_sources': 'Box-score sources',
    }
    if not splits.empty and set(mapping.values()) | {'Other currently out teammates'} <= set(splits):
        # Reject ambiguous multiple rows before filtering. No extrapolation
        # from isolated historical effects to a current simultaneous absence.
        one = splits.loc[~splits.fanduel_id.duplicated(keep=False)]
        one = one.loc[one['Other currently out teammates'].eq(0)].set_index('fanduel_id')
        for target, source in mapping.items():
            out[target] = out.fanduel_id.map(one[source])
    if not matchup.empty:
        if not matchup.fanduel_id.is_unique:
            raise ValueError('Matchup context requires unique player IDs.')
        m = matchup.set_index('fanduel_id')
        for target, source in {
            'shadow_team_pace': 'team_pace48', 'shadow_matchup_pace': 'descriptive_pace_mean',
            'shadow_team_games': 'team_games', 'shadow_opponent_games': 'opponent_games',
            'shadow_opponent_def_rating': 'opponent_def_rating',
            'shadow_team_sources': 'team_sources', 'shadow_opponent_sources': 'opponent_sources',
        }.items():
            out[target] = out.fanduel_id.map(m[source])
    return out


def compare_shadow_forecasts(replay):
    """Fixed 20% rate shrinkage and capped pace sensitivity; exploratory only.

    Each policy is compared to DAILY and reviewed on exactly its supported rows.
    Missing inputs never become a zero or a fallback forecast.
    """
    if not set(FEATURES) <= set(replay):
        return pd.DataFrame()
    required = {'fanduel_id', 'eligible', 'verified_outcome', 'daily_points',
                'adjusted_fd_points', 'adjusted_minutes', 'actual_points', 'nba_source'}
    if not required <= set(replay) or not replay.fanduel_id.is_unique:
        raise ValueError('Use a verified single frozen replay.')
    frame = replay.loc[replay.eligible.astype(str).str.lower().eq('true')
                       & replay.verified_outcome.eq('played')
                       & replay.nba_source.fillna('').ne('')].copy()
    numeric = lambda name: pd.to_numeric(frame[name], errors='coerce').replace([np.inf, -np.inf], np.nan)
    base, minutes, actual, daily = map(numeric, ['adjusted_fd_points', 'adjusted_minutes', 'actual_points', 'daily_points'])
    usable = base.gt(0) & minutes.gt(0) & minutes.le(60) & actual.notna() & daily.notna()
    candidates = {}
    for policy, prefix in zip(POLICIES[:3], ['recent', 'role', 'absence']):
        rate, games, observed_minutes = (numeric(f'shadow_{prefix}_{field}') for field in ['fppm','games','minutes'])
        support = rate.between(0, 5) & games.ge(3) & observed_minutes.ge(60)
        if prefix == 'absence':
            support &= frame.shadow_absence_teammate.fillna('').ne('')
        candidates[policy] = (base * .8 + minutes * rate * .2).where(support)
    team, match = numeric('shadow_team_pace'), numeric('shadow_matchup_pace')
    support = (team.between(50,150) & match.between(50,150)
               & numeric('shadow_team_games').ge(3) & numeric('shadow_opponent_games').ge(3))
    multiplier = (match / team).clip(.95, 1.05).where(support)
    candidates['Pace'] = base * multiplier
    candidates['Recent rate + pace'] = candidates['Recent rate'] * multiplier
    rows = []
    for policy, predicted in candidates.items():
        mask = usable & predicted.notna()
        n = int(mask.sum())
        baseline_error = (base[mask] - actual[mask]).abs()
        error = (predicted[mask] - actual[mask]).abs()
        rows.append({'Policy': policy, 'Eligible played with baseline': int(usable.sum()),
                     'Paired players': n, 'DAILY MAE': (daily[mask]-actual[mask]).abs().mean(),
                     'Reviewed MAE': baseline_error.mean(), 'Shadow MAE': error.mean(),
                     'MAE improvement vs reviewed': (baseline_error-error).mean(),
                     'Shadow bias': (predicted[mask]-actual[mask]).mean()})
    return pd.DataFrame(rows)



def compare_frozen_opportunity(replay):
    """Evaluate two predeclared alternatives on identical verified played rows.

    The minutes scenario starts from DAILY minutes/rate, not already-adjusted
    minutes. The rate scenario holds reviewed minutes fixed and shrinks 20%
    toward the observed rate in the same confirmed role. Never combine them.
    """
    empty = pd.DataFrame({'Policy': OPPORTUNITY_POLICIES, 'Paired players': 0})
    required = set(OPPORTUNITY_FEATURES) | {'fanduel_id','eligible','verified_outcome',
        'nba_source','prelock_starter','daily_points','daily_minutes','adjusted_fd_points',
        'adjusted_minutes','actual_points'}
    if not required <= set(replay):
        return empty
    if replay.fanduel_id.isna().any() or not replay.fanduel_id.is_unique:
        raise ValueError('Use a unique frozen opportunity replay.')
    frame = replay.loc[replay.eligible.astype(str).str.lower().eq('true')
        & replay.verified_outcome.eq('played') & replay.nba_source.fillna('').ne('')].copy()
    num = lambda name: pd.to_numeric(frame[name], errors='coerce').replace([np.inf,-np.inf],np.nan)
    daily, dm, base, m, actual = map(num, ['daily_points','daily_minutes','adjusted_fd_points',
                                        'adjusted_minutes','actual_points'])
    usable = daily.gt(0) & dm.gt(0) & dm.le(48) & base.gt(0) & m.gt(0) & m.le(48) & actual.notna()
    role = frame.shadow_single_absence_role
    support = (role.isin(['starter','bench']) & role.eq(frame.prelock_starter)
        & frame.shadow_single_absence_teammate.fillna('').ne('')
        & frame.shadow_single_absence_sources.fillna('').ne('')
        & num('shadow_single_absence_games').ge(3))
    gap = num('shadow_single_absence_minutes_gap')
    rate = num('shadow_single_absence_fppm')
    forecasts = [
        ((dm + gap).clip(0,48) * daily / dm).where(support & gap.between(-48,48)),
        (.8*base + .2*m*rate).where(support & rate.between(0,5)
            & num('shadow_single_absence_fd_games').ge(3)
            & num('shadow_single_absence_fd_minutes').ge(60)),
    ]
    rows = []
    for policy, predicted in zip(OPPORTUNITY_POLICIES, forecasts):
        mask = usable & predicted.notna()
        error = (predicted[mask] - actual[mask]).abs()
        baseline = (base[mask] - actual[mask]).abs()
        rows.append({'Policy':policy, 'Eligible played with baseline':int(usable.sum()),
            'Paired players':int(mask.sum()), 'DAILY MAE':(daily[mask]-actual[mask]).abs().mean(),
            'Reviewed MAE':baseline.mean(), 'Shadow MAE':error.mean(),
            'MAE improvement vs reviewed':(baseline-error).mean(),
            'Shadow bias':(predicted[mask]-actual[mask]).mean()})
    return pd.DataFrame(rows)


HISTORY_RATE_POLICY = 'Role-aware sample-weighted historical rate'


def historical_rate_shadow(frame):
    """Exploratory prior: select one supported historical rate, not overlapping samples.

    Prefer the same confirmed role when supported; otherwise use recent complete
    games. At least 3 games/60 minutes, shrink toward the current forecast with
    a fixed 240-minute prior and 40% cap. No live scores are modified.
    """
    columns = ['fanduel_id', 'history_rate_fd', 'history_rate_weight', 'history_rate_basis']
    needed = {'fanduel_id', 'eligible', 'adjusted_fd_points', 'adjusted_minutes',
              'prelock_starter', 'prelock_status', 'injury_flag', 'shadow_rate_sources'}
    needed |= {f'shadow_{p}_{v}' for p in ('recent', 'role') for v in ('fppm', 'games', 'minutes')}
    if not needed <= set(frame):
        return pd.DataFrame(columns=columns)
    if frame.fanduel_id.isna().any() or not frame.fanduel_id.is_unique:
        raise ValueError('Historical rate comparison requires unique player IDs.')
    result = frame[['fanduel_id']].copy()
    num = lambda name: pd.to_numeric(frame[name], errors='coerce').replace([np.inf,-np.inf], np.nan)
    base, mins = num('adjusted_fd_points'), num('adjusted_minutes')
    available = (frame.eligible.astype(str).str.lower().eq('true')
                 & ~frame.injury_flag.fillna('').astype(str).str.upper().isin(['O','OUT','Q','D','GTD'])
                 & ~frame.prelock_status.fillna('').astype(str).str.lower().isin(
                     ['out','inactive','suspended','questionable','doubtful'])
                 & frame.shadow_rate_sources.fillna('').astype(str).str.strip().ne('')
                 & base.gt(0) & mins.between(10,48))
    supported = {}
    for prefix in ('recent','role'):
        rate, games, observed = (num(f'shadow_{prefix}_{v}') for v in ('fppm','games','minutes'))
        ok = rate.between(0,5) & games.ge(3) & observed.ge(60) & observed.le(games*60)
        supported[prefix] = (rate, observed, ok)
    recent_rate, recent_mins, recent_ok = supported['recent']
    role_rate, role_mins, role_ok = supported['role']
    role_ok &= frame.prelock_starter.isin(['starter','bench'])
    rate = recent_rate.where(~role_ok, role_rate)
    evidence = recent_mins.where(~role_ok, role_mins)
    use = available & (role_ok | recent_ok)
    weight = (evidence/(evidence+240)).clip(upper=.4).where(use)
    result['history_rate_fd'] = ((1-weight)*base+weight*mins*rate).where(use)
    result['history_rate_weight'] = weight
    result['history_rate_basis'] = np.where(use, np.where(role_ok, 'Confirmed role', 'Recent complete games'), 'Unsupported')
    return result[columns]


def compare_frozen_history_rate(frame):
    """Evaluate the fixed historical policy on verified played outcomes only."""
    report = {'Policy': HISTORY_RATE_POLICY, 'Paired players': 0}
    needed = {'fanduel_id','eligible','verified_outcome','nba_source','actual_points',
              'actual_minutes','daily_points','adjusted_fd_points'}
    if not needed <= set(frame):
        return pd.DataFrame([report])
    shadow = historical_rate_shadow(frame)
    if shadow.empty:
        return pd.DataFrame([report])
    data = frame.merge(shadow,on='fanduel_id',validate='one_to_one')
    cols = ['daily_points','adjusted_fd_points','history_rate_fd','actual_points','actual_minutes']
    data[cols] = data[cols].apply(pd.to_numeric,errors='coerce')
    baseline = (data.eligible.astype(str).str.lower().eq('true') & data.verified_outcome.eq('played')
                & data.nba_source.fillna('').ne('') & data.actual_minutes.between(10,60)
                & np.isfinite(data[['daily_points','adjusted_fd_points','actual_points']]).all(axis=1))
    report['Eligible played with baseline'] = int(baseline.sum())
    matched = data.loc[baseline & np.isfinite(data.history_rate_fd)]
    if matched.empty:
        return pd.DataFrame([report])
    errors = matched[cols[:3]].sub(matched.actual_points,axis=0)
    mae = errors.abs().mean()
    report.update({'Paired players':len(matched),'DAILY MAE':mae.daily_points,
                   'Reviewed MAE':mae.adjusted_fd_points,'Shadow MAE':mae.history_rate_fd,
                   'MAE improvement vs reviewed':mae.adjusted_fd_points-mae.history_rate_fd,
                   'Shadow bias':errors.history_rate_fd.mean()})
    return pd.DataFrame([report])


def component_rate_shadow(frame):
    """Fixed exploratory component forecast; no live scoring or eligibility changes.

    Require complete, self-consistent DAILY box forecasts and one joint historical
    sample. Blend volume, net scoring efficiency and peripheral rate separately.
    Use the existing reviewed minutes once. No assumed team-usage percentage.
    """
    columns = ['fanduel_id','component_shadow_fd','component_basis']
    needed = {'fanduel_id','eligible','prelock_status','prelock_starter','injury_flag',
              'daily_minutes','daily_points','adjusted_fd_points','adjusted_minutes',
              'shadow_rate_sources',*COMPONENT_FIELDS}
    needed |= {'daily_box_'+k for k in COMPONENT_STATS}
    if not needed <= set(frame):
        return pd.DataFrame(columns=columns)
    if frame.fanduel_id.isna().any() or not frame.fanduel_id.is_unique:
        raise ValueError('Component rate review requires unique contest IDs.')
    rows = []
    def n(row, key):
        value = float(row[key])
        if not np.isfinite(value):
            raise ValueError
        return value
    for row in frame.to_dict('records'):
        result = dict(fanduel_id=row['fanduel_id'],component_shadow_fd=None,component_basis='Unsupported')
        rows.append(result)
        if (str(row['eligible']).lower()!='true'
                or str(row['injury_flag']).upper() in {'O','OUT','Q','D','GTD'}
                or str(row['prelock_status']).lower() in {'out','inactive','suspended','questionable','doubtful'}
                or not isinstance(row['shadow_rate_sources'],str) or not row['shadow_rate_sources'].strip()):
            continue
        try:
            dm,m,base,daily = (n(row,k) for k in ('daily_minutes','adjusted_minutes','adjusted_fd_points','daily_points'))
            d = {k:n(row,'daily_box_'+k) for k in COMPONENT_STATS}
            if not (10<=dm<=48 and 10<=m<=48 and base>0 and daily>0
                    and all(0<=v<=150 for v in d.values())):
                continue
            o = d['fieldGoalsAttempted']+.44*d['freeThrowsAttempted']+d['turnovers']
            net = d['points']-d['turnovers']
            peripheral = 1.2*d['rebounds']+1.5*d['assists']+3*(d['steals']+d['blocks'])
            if not (o>0 and abs(net+peripheral-daily)<=.5
                    and 0<o/dm<=2 and -1<=net/o<=4 and 0<=peripheral/dm<=4):
                continue
        except (TypeError,ValueError,KeyError):
            continue
        role = row['prelock_starter']
        for prefix in ([role,'recent'] if role in ('starter','bench') else ['recent']):
            try:
                g,h,vol,eff,per = (n(row,f'component_{prefix}_{k}') for k in
                    ('games','minutes','opportunities_per_minute','net_per_opportunity','peripheral_per_minute'))
                if not (g>=3 and 60<=h<=60*g and 0<vol<=2 and -1<=eff<=4 and 0<=per<=4):
                    continue
                # Fixed 20% component shrinkage. Preserve reviewed-vs-DAILY rate
                # adjustments, adding only the component-model change in rate.
                volume=.8*o/dm+.2*vol
                efficiency=.8*net/o+.2*eff
                peripherals=.8*peripheral/dm+.2*per
                delta=volume*efficiency+peripherals-(net+peripheral)/dm
                forecast=base+m*delta
                if 0<forecast<=150:
                    result.update(component_shadow_fd=forecast,component_basis=prefix)
                break
            except (TypeError,ValueError,KeyError):
                continue
    return pd.DataFrame(rows,columns=columns)


def compare_frozen_component_rate(frame):
    report = {'Policy':COMPONENT_POLICY,'Paired players':0}
    needed = {'fanduel_id','eligible','verified_outcome','nba_source','actual_minutes',
              'actual_points','daily_points','adjusted_fd_points'}
    if not needed <= set(frame):
        return pd.DataFrame([report])
    prediction = component_rate_shadow(frame)
    if prediction.empty:
        return pd.DataFrame([report])
    data=frame.merge(prediction,on='fanduel_id',validate='one_to_one')
    cols=['daily_points','adjusted_fd_points','component_shadow_fd','actual_points','actual_minutes']
    data[cols]=data[cols].apply(pd.to_numeric,errors='coerce')
    base=(data.eligible.astype(str).str.lower().eq('true') & data.verified_outcome.eq('played')
          & data.nba_source.fillna('').ne('') & data.actual_minutes.between(10,60)
          & np.isfinite(data[['daily_points','adjusted_fd_points','actual_points']]).all(axis=1))
    report['Eligible played with baseline']=int(base.sum())
    matched=data.loc[base & np.isfinite(data.component_shadow_fd)]
    if not matched.empty:
        errors=matched[cols[:3]].sub(matched.actual_points,axis=0)
        mae=errors.abs().mean()
        report.update({'Paired players':len(matched),'DAILY MAE':mae.daily_points,
                       'Reviewed MAE':mae.adjusted_fd_points,'Shadow MAE':mae.component_shadow_fd,
                       'MAE improvement vs reviewed':mae.adjusted_fd_points-mae.component_shadow_fd,
                       'Shadow bias':errors.component_shadow_fd.mean()})
    return pd.DataFrame([report])
