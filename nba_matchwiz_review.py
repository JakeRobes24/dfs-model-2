"""Exploratory review of frozen MatchWiz references; publication time unverified."""
import json
import pandas as pd
from matchwiz_reference import MATCHWIZ
from nba_distribution_review import bounded, timestamp
from slate_import import matchup_key, team_code, contest_player_keys, player_key

FIELDS = ['fanduel_id','outcome','reference_role','retrieved_at','forecast','actual',
          'daily','reviewed','reference_error','daily_error','reviewed_error']


def review_matchwiz(replay):
    """Minutes-only evaluation, including a separate played and DNP breakdown."""
    if 'matchwiz_reference_json' not in replay:
        return pd.DataFrame(columns=FIELDS)
    required = {'fanduel_id','fanduel_name','team','game','slate_date','eligible','verified_outcome',
                'actual_minutes','daily_minutes','adjusted_minutes','replay_captured_at_utc',
                'replay_cutoff_utc','replay_timing','replay_before_full_slate_tip'}
    if not required <= set(replay) or not replay.fanduel_id.is_unique or replay.fanduel_id.isna().any():
        raise ValueError('MatchWiz review requires a unique frozen replay.')
    output = []
    for row in replay.itertuples():
        if (str(row.eligible).lower() != 'true' or str(row.replay_before_full_slate_tip).lower() != 'true'
                or row.replay_timing != 'before_scheduled_tip'
                or row.verified_outcome not in ('played','did_not_play')):
            continue
        capture, tip = timestamp(row.replay_captured_at_utc), timestamp(row.replay_cutoff_utc)
        if capture is None or tip is None or capture >= tip:
            continue
        try:
            note = json.loads(row.matchwiz_reference_json)
        except (TypeError, ValueError):
            continue
        if (not isinstance(note,dict) or note.get('source') != MATCHWIZ
                or note.get('publication_time_verified') is not False
                or note.get('slate_date') != str(row.slate_date)
                or note.get('fanduel_id') != row.fanduel_id
                or team_code(note.get('team','')) != team_code(row.team)
                or matchup_key(note.get('game','')) != matchup_key(row.game)
                or player_key(note.get('player','')) not in contest_player_keys(row.fanduel_name,row.fanduel_id)):
            continue
        retrieved = timestamp(note.get('retrieved_at'))
        forecast = bounded(note.get('reference_minutes'),0,48)
        if (retrieved is None or not capture-pd.Timedelta(hours=6) <= retrieved <= capture
                or retrieved.tz_convert('America/New_York').date().isoformat() != str(row.slate_date)
                or forecast is None):
            continue
        actual = 0.0 if row.verified_outcome == 'did_not_play' else bounded(row.actual_minutes,0,90)
        if actual is None:
            continue
        daily = bounded(row.daily_minutes,0,60)
        reviewed = bounded(row.adjusted_minutes,0,60)
        output.append([row.fanduel_id,row.verified_outcome,note.get('reference_role','unverified'),
                       retrieved.isoformat(),forecast,actual,daily,reviewed,forecast-actual,
                       None if daily is None else daily-actual,
                       None if reviewed is None else reviewed-actual])
    return pd.DataFrame(output,columns=FIELDS)


def summarize_matchwiz(details):
    rows = []
    for label, group in [('All verified outcomes',details),('Played',details.loc[details.outcome.eq('played')]),
                         ('Verified DNP',details.loc[details.outcome.eq('did_not_play')])]:
        if group.empty:
            continue
        paired = group.dropna(subset=['daily_error','reviewed_error'])
        rows.append(dict(sample=label,forecasts=len(group),paired_forecasts=len(paired),
                         reference_mae=group.reference_error.abs().mean(),
                         reference_bias=group.reference_error.mean(),
                         reference_mae_paired=paired.reference_error.abs().mean(),
                         daily_mae_paired=paired.daily_error.abs().mean(),
                         reviewed_mae_paired=paired.reviewed_error.abs().mean(),
                         evidence_status='Exploratory: retrieval time verified, publication unverified'))
    return pd.DataFrame(rows)
