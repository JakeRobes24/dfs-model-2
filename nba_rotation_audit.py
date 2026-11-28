"""Audit archive-only rotation alerts and reconcile final substitution clocks."""
from collections import defaultdict
from math import isfinite
import re

import numpy as np
import pandas as pd

from nba_historical_roles import espn_roles
from slate_import import player_key


def _clock(value):
    if not re.fullmatch(r'(?:\d{1,2}:)?\d{1,2}(?:\.\d+)?', value):
        raise ValueError('Unrecognized play clock.')
    parts = value.split(':')
    if len(parts)==2 and float(parts[-1])>=60:
        raise ValueError('Unrecognized play clock.')
    return float(parts[-1])+60*int(parts[0]) if len(parts) == 2 else float(value)


def _elapsed(play):
    period = play['period']['number']
    if type(period) is not int or period < 1:
        raise ValueError('Play outside its period.')
    length = 720 if period <= 4 else 300
    seconds = _clock(play['clock']['displayValue'])
    if not 0 <= seconds <= length:
        raise ValueError('Play outside its period.')
    return 720*min(period-1, 4)+300*max(period-5, 0)+length-seconds


def final_rotation(payload, event_id, away, home, *, only_player=None):
    """Require logged substitutions and reconciled minutes on the requested scope."""
    expected = espn_roles(payload, event_id, away, home)
    comp = payload['header']['competitions'][0]
    clubs = {str(c['team']['id']): away if c['homeAway'] == 'away' else home for c in comp['competitors']}
    final_score = {c['homeAway']: int(float(c['score'])) for c in comp['competitors']}
    players, active, counts = {}, {away:set(), home:set()}, defaultdict(lambda: [0.]*6)
    for group in payload['boxscore']['players']:
        club = clubs[str(group['team']['id'])]
        for stat in group['statistics']:
            if 'MIN' not in stat['labels']:
                continue
            for entry in stat['athletes']:
                athlete = entry['athlete']
                key = player_key(athlete['displayName'])
                if key not in expected[club]:
                    continue
                pid = str(athlete['id'])
                if pid in players:
                    raise ValueError('Ambiguous substitution identity.')
                players[pid] = (club, key)
                if expected[club][key][1]:
                    active[club].add(pid)
    if any(len(on_court) != 5 for on_court in active.values()):
        raise ValueError('Incomplete starting lineup.')
    if only_player is not None:
        tracked = {pid for pid, (_,key) in players.items() if key == player_key(only_player)}
        if len(tracked) != 1:
            raise ValueError('Missing or ambiguous requested player.')
        for on_court in active.values():
            on_court.intersection_update(tracked)
    else:
        tracked = set(players)

    # Allocate each elapsed step using the last logged score and active five.
    prior_time, prior_period, score = 0., 1, (0,0)
    plays = payload['plays']
    if not plays or plays[-1]['type']['text'] != 'End Game':
        raise ValueError('Play feed lacks final marker.')
    seen = set()
    for play in plays:
        if play['id'] in seen:
            raise ValueError('Duplicate play identity.')
        seen.add(play['id'])
        now, period = _elapsed(play), play['period']['number']
        delta = now-prior_time
        if delta < 0 or period not in (prior_period,prior_period+1):
            raise ValueError('Nonchronological play feed.')
        if period != prior_period and abs(prior_time-(720*min(prior_period,4)+300*max(prior_period-4,0))) > .001:
            raise ValueError('Missing end-of-period clock.')
        margin = abs(score[0]-score[1])
        for pid in active[away] | active[home]:
            record = counts[pid]
            record[0] += delta
            if period <= 4:
                record[period] += delta
            if period == 4 and margin >= 15:
                record[5] += delta
        if play['type']['text'] == 'Substitution':
            pair = [str(p['athlete']['id']) for p in play['participants']]
            club = clubs[str(play['team']['id'])]
            if only_player is None or tracked.intersection(pair):
                if (len(pair) != 2 or any(pid not in players or players[pid][0] != club for pid in pair)
                        or pair[0] in active[club] or (pair[1] in tracked and pair[1] not in active[club])):
                    raise ValueError('Substitution inconsistent with active lineup.')
                if pair[1] in tracked:
                    active[club].remove(pair[1])
                if pair[0] in tracked:
                    active[club].add(pair[0])
        score = (play['awayScore'],play['homeScore'])
        prior_time, prior_period = now, period
    if (score != (final_score['away'],final_score['home'])
            or prior_time != 2880+300*max(0,prior_period-4)):
        raise ValueError('Play feed did not reconcile to final game.')

    output = []
    for pid, (club,key) in players.items():
        if pid not in tracked:
            continue
        total, q1, q2, q3, q4, large_q4 = counts[pid]
        minutes, starter = expected[club][key]
        if abs(minutes-total/60)>1.01:
            raise ValueError('Substitution minutes disagree with final box.')
        output.append(dict(team=club, key=key, started=starter, seconds=total,
                           scope='one player' if only_player is not None else 'complete game',
                           q1_seconds=q1,q2_seconds=q2,q3_seconds=q3,q4_seconds=q4,
                           q4_large_margin_seconds=large_q4))
    return output


def rotation_watch(rows):
    """Fixed diagnostic rule. Positive 6-minute errors are downside misses."""
    columns = ['forecast_minutes','actual_minutes','recent_minutes','prior_minutes_sd','forecast_fd','actual']
    if (rows[['date','id']].isna().any().any() or rows.duplicated(['date','id']).any()
            or rows.history_latest.isna().any() or not rows.history_latest.lt(rows.date).all()):
        raise ValueError('Rotation inputs must have unique contest IDs and earlier history.')
    work = rows.loc[np.isfinite(rows[columns]).all(axis=1)
                    & rows.forecast_minutes.ge(24) & rows.actual_minutes.gt(0)].copy()
    work['minutes_error'] = work.forecast_minutes-work.actual_minutes
    work['history_gap'] = work.forecast_minutes-work.recent_minutes
    work['over_six'] = work.minutes_error.ge(6)
    work['miss_six'] = work.minutes_error.abs().ge(6)
    work['expanded_role'] = work.history_gap.ge(6)
    work['volatile_role'] = work.prior_minutes_sd.ge(6)
    return work


def forward_minutes_shadow(watched, *, minimum_training=20, minimum_gap=6.):
    """Fit shrinkage only on flagged rows on at least two earlier slates."""
    if type(minimum_training) is not int or minimum_training < 1:
        raise ValueError('Minimum earlier row count must be positive.')
    if not isfinite(minimum_gap) or minimum_gap < 0:
        raise ValueError('Minimum forecast gap must be finite and nonnegative.')
    watched = watched.assign(shadow_eligible=watched.history_gap.gt(0)&watched.history_gap.ge(minimum_gap))
    output = []
    for date, rows in watched.groupby('date', sort=True):
        prior = watched.loc[watched.date.lt(date) & watched.shadow_eligible]
        if prior.date.nunique()<2 or len(prior)<minimum_training:
            continue
        x, y = prior.history_gap, prior.minutes_error
        weight = prior.date.map(1/prior.date.value_counts())
        share = float(np.clip((weight*x*y).sum()/(weight*x*x).sum(),0.,1.))
        shadow = rows.forecast_minutes-share*rows.history_gap.where(rows.shadow_eligible,0.)
        output.append(rows.assign(shadow_minutes=shadow, shadow_fd=rows.forecast_fd*shadow/rows.forecast_minutes,
                                  earlier_rows=len(prior), fraction_removed=share))
    return pd.concat(output,ignore_index=True) if output else pd.DataFrame()
