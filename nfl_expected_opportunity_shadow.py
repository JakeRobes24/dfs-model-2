"""Freeze the previously tested NFL scoring-channel challenger before kickoff.

No live scoring, optimizer substitution, or certification. The packet is an
explicit reviewer-attested join of prior workload and expected-stat sources;
the caller must verify independent identities, publication and team schedule.
"""
from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
import math
from statistics import mean

from nfl_expected_opportunity_validation import COMPONENTS, MATCH_FIELDS
from nfl_projection_review import stamp
from nfl_daily_audit import team, game

POLICY_VERSION = '2026-11-28-fixed-channel-v1'
WEIGHTS = {'receiving': .75, 'rushing': 1.}
UNAVAILABLE = {'out','inactive','suspended','ir','questionable','doubtful','q','d','o','gtd'}


def finite(v):
    return type(v) in (float,int) and math.isfinite(v)


def text(v):
    return isinstance(v,str) and bool(v.strip())


def score_channel(row, channel):
    """The same component weights and matching conditions as the replay."""
    volume, yards, provider_volume, provider_yards = MATCH_FIELDS[channel]
    weights=COMPONENTS[channel]
    actual=row.get('actual_components',{})
    expected=row.get('expected_components',{})
    workload=row.get('workload',{})
    if not all(isinstance(v,dict) for v in (actual,expected,workload)):
        return None
    required=[*weights,provider_volume]
    if (any(not finite(actual.get(k)) for k in required)
        or any(not finite(expected.get(k)) for k in weights)
        or any(not finite(workload.get(k)) for k in (volume,yards))):
        return None
    if (workload[volume]!=actual[provider_volume] or workload[yards]!=actual[provider_yards]
        or not 0<=workload[volume]<=85):
        return None
    for values in (actual,expected):
        if any(abs(values[k])>350 or ('yards' not in k and values[k]<0) for k in weights):
            return None
    return (workload[volume],sum(actual[k]*v for k,v in weights.items()),
            sum(expected[k]*v for k,v in weights.items()))


def freeze_expected_opportunity(audit, packet, *, frozen_at):
    """Retain a channel forecast on exact prior four consecutive team games.

    Packet metadata is reviewer-attested, not automatically authenticated.
    Require the actual freeze clock, verified historical source timestamps,
    exact contest input fingerprints, and no prior row after that clock.
    Missing/invalid support is explicit. This is not a full FD forecast.
    """
    freeze=stamp(frozen_at)
    cutoff=stamp(packet['cutoff_utc'])
    slate=date.fromisoformat(packet['slate_date'])
    season=packet.get('season')
    if type(season) is not int or season not in (slate.year,slate.year-1):
        raise ValueError('Explicit regular-season year required')
    if freeze>cutoff:
        raise ValueError('Freeze cannot occur after decision cutoff')
    if (packet.get('schema')!=1 or packet.get('contest_id')!=audit['contest_id']
        or any(packet.get(k)!=audit.get(k) or not isinstance(audit.get(k),str)
               or len(audit[k])!=64 or any(c not in '0123456789abcdef' for c in audit[k])
               for k in ('contest_sha256','daily_sha256'))):
        raise ValueError('Exact original contest and DAILY fingerprints required')
    if not isinstance(packet.get('players'),list) or not isinstance(audit.get('players'),list):
        raise ValueError('Expected explicit player lists')
    players={p['player_id']:p for p in audit['players']}
    if len(players)!=len(audit['players']):
        raise ValueError('Duplicate contest player ID')
    inputs={}
    ids=set()
    for r in packet['players']:
        pid=r.get('player_id')
        if pid not in players or pid in inputs:
            raise ValueError('Duplicate or noncontest history player')
        gsis=r.get('gsis_id')
        if not text(gsis) or gsis in ids:
            raise ValueError('Unique reviewed stable player identity required')
        ids.add(gsis)
        inputs[pid]=r
    rows=[]
    for pid,p in players.items():
        if len(p['positions'])!=1 or p['positions'][0] not in ('RB','WR','TE'):
            continue
        record=inputs.get(pid)
        reason=None
        if str(p['status']).strip().lower() in UNAVAILABLE:
            reason='uncertain_or_unavailable_contest_status'
        elif record is None:
            reason='no_history_packet'
        elif (record.get('identity_verified') is not True or record.get('schedule_verified') is not True
              or team(record.get('team'))!=team(p['team'])
              or game(record.get('game'))!=game(p['game'])
              or record.get('position')!=p['positions'][0]):
            reason='unverified_identity_or_schedule'
        if reason:
            rows.append(dict(player_id=pid,player=p['player'],support=reason,channels={}))
            continue
        target=stamp(record['kickoff_utc'])
        if not freeze<=cutoff<target or target.date()<slate:
            raise ValueError('Require freeze and cutoff before scheduled kickoff')
        from zoneinfo import ZoneInfo
        if target.astimezone(ZoneInfo('America/New_York')).date()!=slate:
            raise ValueError('Kickoff outside exact slate date')
        n=record.get('team_game_number')
        if type(n) is not int or not 5<=n<=18:
            raise ValueError('Valid target team game number required')
        history=record.get('history')
        if not isinstance(history,list):
            raise ValueError('Expected complete prior history list')
        seqs=[x.get('team_game_number') for x in history]
        if any(type(x) is not int or not 1<=x<n for x in seqs) or len(seqs)!=len(set(seqs)):
            raise ValueError('Duplicate, invalid or future history game number')
        by_seq={x['team_game_number']:x for x in history}
        prior=[by_seq.get(i) for i in range(n-4,n)]
        if any(r is None for r in prior):
            rows.append(dict(player_id=pid,player=p['player'],support='missing_consecutive_prior_games',channels={}))
            continue
        dates=[]
        valid=True
        games=set()
        for r in prior:
            day=date.fromisoformat(r['game_date'])
            dates.append(day)
            gid=r.get('game_id')
            if (r.get('gsis_id')!=record['gsis_id'] or team(r.get('team'))!=team(p['team'])
                or r.get('position')!=p['positions'][0] or r.get('season_type')!='regular'
                or r.get('season')!=season
                or r.get('participation')!='played' or not text(gid) or gid in games
                or day>=slate or not all(text(r.get(k)) for k in
                    ('workload_source','expected_source','expected_record_id','workload_record_id'))
                or r.get('source_identity_verified') is not True
                or r.get('expected_provenance_verified') is not True):
                valid=False
                break
            games.add(gid)
            try:
                end=stamp(r['game_final_at'])
                pub=stamp(r['expected_published_at'])
                observed=stamp(r['expected_observed_at'])
                workload_obs=stamp(r['workload_observed_at'])
                if (end.date()<day or not end<=pub<=observed<=freeze
                    or not end<=workload_obs<=freeze):
                    valid=False
                    break
            except (ValueError,KeyError,TypeError):
                valid=False
                break
        if not valid or dates!=sorted(set(dates)):
            rows.append(dict(player_id=pid,player=p['player'],support='unverified_prior_provenance',channels={}))
            continue
        channels={}
        for channel,weight in WEIGHTS.items():
            scored=[score_channel(r,channel) for r in prior]
            if any(x is None for x in scored) or sum(x[0] for x in scored)<4:
                continue
            actual=mean(x[1] for x in scored)
            expected=mean(x[2] for x in scored)
            channels[channel]=dict(actual_average=actual,expected_average=expected,
                                   challenger=(1-weight)*actual+weight*expected,
                                   expected_weight=weight,prior_opportunities=sum(x[0] for x in scored))
        rows.append(dict(player_id=pid,player=p['player'],team=p['team'],game=p['game'],
                         gsis_id=record['gsis_id'],position=p['positions'][0],
                         support='channel_forecast' if channels else 'missing_matched_components',
                         prior_game_ids=[r['game_id'] for r in prior],channels=channels))
    # Persist the exact input packet digest and the explicit forecast values;
    # downstream evaluation must retain the original packet as well.
    digest=sha256(json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(policy_version=POLICY_VERSION,contest_id=audit['contest_id'],
                contest_sha256=audit['contest_sha256'],daily_sha256=audit['daily_sha256'],
                history_packet_sha256=digest,slate_date=packet['slate_date'],season=season,
                cutoff_utc=packet['cutoff_utc'],frozen_at=freeze.isoformat(),rows=rows,
                certified=False,warning='Reviewer-attested channel-only shadow forecasts; no full FD or optimizer substitution.')
