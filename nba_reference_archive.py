"""Freeze reference-board numerical evidence, separate from accepted scoring.

Keep exact eligible matches, explicit publication timestamp (or unknown),
retrieval/observation time and source status. Never promote reference rows to
independent votes or claim their publication date from retrieval time.
"""
import json
from datetime import date
from collections import defaultdict
import pandas as pd
from nba_distribution_review import bounded,timestamp
from research_source_registry import NBA_REFERENCE_BOARDS, NBA_MINUTES_REFERENCE_BOARDS, RESEARCH_LINKS
from slate_research import match_public,compare_reference,compare_keelstats

PROVIDERS=NBA_REFERENCE_BOARDS
FIELDS=('replay_reference_forecasts_json','replay_reference_coverage_json')

def freeze_reference_boards(pool,boards,status,slate,observed_at):
    if type(slate) is not date or not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any():
        raise ValueError('Require exact dated unique contest pool')
    cutoff=timestamp(observed_at)
    if cutoff is None:
        raise ValueError('Reference observation requires timezone')
    eligible=set(pool.loc[pool.eligible.astype(str).str.lower().eq('true'),'fanduel_id'])
    matched_by_player=defaultdict(list)
    counts=[]
    for name in PROVIDERS:
        row=dict(provider=name,access_url=RESEARCH_LINKS[name],
                 status=str(status.get(name,'Not checked this refresh')),returned_rows=None,
                 matched_players=None,fresh_dated_players=None,publication_unknown_players=None,
                 eligible_players=len(eligible),scope='Reference only; not an independent scoring vote')
        if name not in boards:
            counts.append(row)
            continue
        records,stamp=boards[name][:2]
        row['returned_rows']=len(records)
        published=timestamp(stamp)
        row.update(matched_players=0,fresh_dated_players=0,publication_unknown_players=0)
        if cutoff.tz_convert('America/New_York').date()!=slate:
            row['status']='Reference observation not on selected slate date'
            counts.append(row)
            continue
        if stamp is not None and (published is None or published>cutoff):
            row['status']='Reference publication timestamp invalid or future'
            counts.append(row)
            continue
        try:
            if name=='LineupExperts':
                compared=pd.DataFrame(match_public(pool,records))
                if not compared.empty:
                    compared=compared.drop_duplicates('fanduel_id',keep=False).assign(
                        reference_points=lambda rows: rows['reference_fd'])
            elif name in NBA_MINUTES_REFERENCE_BOARDS:
                compared=compare_keelstats(pool,records)
            else:
                compared=compare_reference(pool,records)
            if not compared.empty:
                for item in compared.to_dict('records'):
                    pid=item['fanduel_id']
                    if pid not in eligible:
                        continue
                    fp=bounded(item.get('reference_points'),0,150)
                    minutes=bounded(item.get('reference_minutes'),0,48)
                    if fp is None and minutes is None:
                        continue
                    observed = cutoff
                    if name in ('Edgehalla','MatchWiz'):
                        observed = timestamp(item.get('retrieved_at'))
                        if (observed is None or not cutoff-pd.Timedelta(hours=6)<=observed<=cutoff
                                or observed.tz_convert('America/New_York').date() != slate
                                or item.get('slate_date') != slate.isoformat()):
                            continue
                    freshness=('Publication unknown' if published is None else
                               'Dated within six hours' if cutoff-pd.Timedelta(hours=6)<=published
                               else 'Dated but stale')
                    entry=dict(provider=name,source=RESEARCH_LINKS[name],
                        observed_at=observed.isoformat(),published_at=published.isoformat() if published is not None else None,
                        slate_date=slate.isoformat(),freshness=freshness,fd_points=fp,minutes=minutes,
                        scoring_accepted=False)
                    if name == 'Edgehalla':
                        entry.update(conditional_on_playing=True, fd_points_basis='FanDuel from projected box components')
                    # Keep raw reported components; never fill an absent stat with zero.
                    if name in ('Edgehalla','MatchWiz'):
                        fields = ({'points':'reference_pts','rebounds':'reference_reb','assists':'reference_ast'}
                                  if name=='MatchWiz' else {'points':'reference_pts', **{k:'reference_'+k for k in
                                  ('rebounds','assists','steals','blocks','turnovers')}})
                        components={k:bounded(item.get(col),0,150) for k,col in fields.items()}
                        components={k:v for k,v in components.items() if v is not None}
                        if components:
                            entry['components']=components
                            entry['components_basis']='Projected box-score counts; missing components remain absent'
                        if name=='MatchWiz':
                            entry['fd_points']=None
                            role=item.get('reference_role')
                            if role in ('starter listing','nonstarter listing'):
                                entry['reference_role']=role
                    matched_by_player[pid].append(entry)
                    row['matched_players']+=1
                    row['fresh_dated_players']+=int(freshness=='Dated within six hours')
                    row['publication_unknown_players']+=int(freshness=='Publication unknown')
        except (ValueError,TypeError,KeyError,AttributeError):
            row['status']='Reference matching could not be verified'
            for entries in matched_by_player.values():
                entries[:]=[e for e in entries if e['provider']!=name]
            row.update(matched_players=0,fresh_dated_players=0,publication_unknown_players=0)
        counts.append(row)
    receipt=dict(version=1,slate_date=slate.isoformat(),observed_at=cutoff.isoformat(),providers=counts,
                 warning='Observation time of cached reference board, not fetch or publication proof. Unknown is not zero; reference rows are not independent consensus.')
    out=pool.assign(replay_reference_forecasts_json=pool.fanduel_id.map(
        lambda pid:json.dumps(matched_by_player.get(pid,[]),sort_keys=True,allow_nan=False)),
        replay_reference_coverage_json=json.dumps(receipt,sort_keys=True,allow_nan=False))
    return out,pd.DataFrame(counts)
