"""Grade the exact frozen expected-opportunity receipt on final played outcomes."""
from collections import defaultdict
from statistics import mean
from nfl_expected_opportunity_shadow import (
    freeze_expected_opportunity, COMPONENTS, finite, text, stamp, team, game,
)

POLICIES=('actual_average','expected_average','challenger')


def compare_frozen_opportunity(audit, packet, receipt, actuals):
    """Verify original inputs and arithmetic, never reconstruct absent forecasts.

    Caller must retain the actual pregame receipt and independently verified
    final outcome identities. Recalculation proves consistency, not capture time.
    Outcomes have explicit complete channel stats; missing values are not zeros.
    """
    if receipt != freeze_expected_opportunity(audit,packet,frozen_at=receipt['frozen_at']):
        raise ValueError('Frozen receipt does not reproduce from original inputs')
    inputs={r['player_id']:r for r in packet['players']}
    pool={r['player_id']:r for r in audit['players']}
    by_id={}
    stable=set()
    for a in actuals:
        pid=a.get('player_id')
        if pid not in pool or pid in by_id or not text(a.get('gsis_id')):
            raise ValueError('Require unique on-contest outcome IDs')
        token=(a['gsis_id'],game(a.get('game')))
        if token in stable:
            raise ValueError('Duplicate stable player/game outcome')
        stable.add(token)
        by_id[pid]=a
    coverage=defaultdict(int)
    details=[]
    groups=defaultdict(list)
    for r in receipt['rows']:
        if not r['channels']:
            coverage['unsupported_forecast']+=1
            continue
        pid=r['player_id']
        a=by_id.get(pid)
        if a is None:
            coverage['missing_outcome']+=1
            continue
        original=inputs[pid]
        if (a.get('identity_verified') is not True or not text(a.get('source'))
                or not text(a.get('source_record_id')) or not text(a.get('official_game_id'))
                or a['gsis_id']!=r['gsis_id'] or team(a.get('team'))!=team(r['team'])
                or game(a.get('game'))!=game(r['game']) or a.get('position')!=r['position']
                or a.get('season')!=receipt['season'] or a.get('game_date')!=receipt['slate_date']
                or stamp(a['kickoff_utc'])!=stamp(original['kickoff_utc'])):
            raise ValueError('Outcome identity, source or kickoff mismatch')
        if a.get('final') is not True:
            coverage['unverified_final']+=1
            continue
        if not stamp(a['kickoff_utc'])<stamp(a['final_at'])<=stamp(a['observed_at']):
            raise ValueError('Invalid final outcome chronology')
        if a.get('participation')!='played':
            coverage['nonplay_or_unknown']+=1
            continue
        components=a.get('components',{})
        matched=0
        for channel,forecast in r['channels'].items():
            weights=COMPONENTS[channel]
            if (not isinstance(components,dict) or any(
                    not finite(components.get(k)) or abs(components[k])>350
                    or int(components[k])!=components[k]
                    or ('yards' not in k and components[k]<0) for k in weights)):
                coverage['missing_or_invalid_channel']+=1
                continue
            actual=sum(components[k]*w for k,w in weights.items())
            detail=dict(player_id=pid,position=r['position'],game=r['game'],
                        channel=channel,actual=actual,
                        forecasts={p:forecast[p] for p in POLICIES})
            details.append(detail)
            for label in ('all',r['position']):
                groups[(channel,label)].append(detail)
            matched+=1
        coverage['matched_played' if matched else 'no_complete_channel']+=1
    summary=[]
    for (channel,position),sample in sorted(groups.items()):
        row=dict(channel=channel,position=position,n=len(sample),errors={})
        for p in POLICIES:
            errors=[v['forecasts'][p]-v['actual'] for v in sample]
            row['errors'][p]=dict(mae=mean(abs(e) for e in errors),bias=mean(errors),
                                  rmse=mean(e*e for e in errors)**.5)
        row['improved']=sum(abs(v['forecasts']['challenger']-v['actual'])<
                            abs(v['forecasts']['actual_average']-v['actual']) for v in sample)
        row['worsened']=sum(abs(v['forecasts']['challenger']-v['actual'])>
                            abs(v['forecasts']['actual_average']-v['actual']) for v in sample)
        summary.append(row)
    return dict(contest_id=receipt['contest_id'],policy_version=receipt['policy_version'],
                frozen_at=receipt['frozen_at'],coverage=dict(coverage),summary=summary,
                matched_channels=details,certified=False,
                warning='Played-only matched channels; no full FD, no proof of authentic pregame timestamp.')
