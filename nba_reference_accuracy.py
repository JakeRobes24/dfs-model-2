"""Evaluate archived numerical reference forecasts without treating them as votes.

Publication-unverified or stale references remain visible in coverage but never
enter the dated accuracy sample. These are played-only descriptive comparisons:
provider conditional/unconditional semantics and provenance may differ.
"""
from collections import defaultdict
from datetime import date
import json
import pandas as pd
from nba_distribution_review import bounded,timestamp
from nba_reference_archive import PROVIDERS
from research_source_registry import RESEARCH_LINKS

DETAIL_FIELDS=('slate_date','fanduel_id','provider','metric','published_at','observed_at',
               'forecast','actual','daily','reviewed','source_error','daily_error','reviewed_error')
NEWS={'out','inactive','suspended','available','probable','questionable','doubtful'}

def _records(value):
    try:
        rows=json.loads(value)
        if isinstance(rows,list) and all(isinstance(r,dict) for r in rows):
            return rows
    except (ValueError,TypeError):
        pass
    return None

def review_reference_dates(frame,target_day):
    """Return matched detail, daily and equal-date summaries plus exclusions.

    All rows in a date must be a single exact full-slate pre-tip capture.
    Team-level status/role news invalidates older reference estimates. Unknown
    actuals and DNPs are excluded, not zeroed. No live scoring changes.
    """
    detail=[]
    coverage=[]
    if frame.empty or 'replay_reference_forecasts_json' not in frame:
        return pd.DataFrame(columns=DETAIL_FIELDS),pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    required={'slate_date','fanduel_id','team','game','eligible','verified_outcome',
        'nba_source','actual_points','actual_minutes','daily_points','daily_minutes',
        'adjusted_fd_points','adjusted_minutes','replay_captured_at_utc','replay_cutoff_utc',
        'replay_timing','replay_before_full_slate_tip','replay_evidence_json'}
    if not required<=set(frame):
        raise ValueError('Require dated full-pool frozen replay fields')
    target=pd.Timestamp(target_day)
    dates=pd.to_datetime(frame.slate_date,errors='coerce')
    if target.tzinfo is not None or dates.isna().any() or (dates.dt.normalize()>=target.normalize()).any():
        raise ValueError('Reference review requires strictly earlier dates')
    for day,g in frame.assign(_day=dates.dt.date).groupby('_day',sort=True):
        ids=g.fanduel_id.astype(str)
        captures=[timestamp(v) for v in g.replay_captured_at_utc]
        tips=[timestamp(v) for v in g.replay_cutoff_utc]
        if (not ids.is_unique or not ids.str.fullmatch(r'[0-9]+-[0-9]+').all()
            or ids.str.split('-').str[0].nunique()!=1 or len(set(captures))!=1
            or any(a is None or b is None or a>=b or b.tz_convert('America/New_York').date()!=day
                   for a,b in zip(captures,tips))
            or not g.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()
            or not g.replay_timing.eq('before_scheduled_tip').all()):
            raise ValueError(f'{day}: require one exact full-slate pre-tip capture')
        capture=captures[0]
        latest_news={}
        invalid=set()
        for r in g.itertuples():
            key=(r.team,r.game)
            notes=_records(r.replay_evidence_json)
            if notes is None:
                invalid.add(key)
                continue
            for note in notes:
                if note.get('official') is not True or (
                    str(note.get('status','')).lower() not in NEWS
                    and str(note.get('starter','')).lower() not in {'starter','bench'}):
                    continue
                stamp=timestamp(note.get('observed_at'))
                if stamp is None or stamp>capture:
                    invalid.add(key)
                    continue
                latest_news[key]=max(latest_news.get(key,stamp),stamp)
        counters={p:defaultdict(int) for p in PROVIDERS}
        eligible=0
        for r in g.itertuples():
            if str(r.eligible).lower()!='true':
                continue
            eligible+=1
            records=_records(r.replay_reference_forecasts_json)
            if records is None:
                continue
            by_provider=defaultdict(list)
            for e in records:
                if e.get('provider') in counters:
                    by_provider[e['provider']].append(e)
            for provider,entries in by_provider.items():
                count=counters[provider]
                count['archived_players']+=1
                if len(entries)!=1:
                    count['ambiguous']+=1
                    continue
                e=entries[0]
                obs=timestamp(e.get('observed_at'))
                pub=timestamp(e.get('published_at'))
                if (e.get('source')!=RESEARCH_LINKS[provider] or e.get('scoring_accepted') is not False
                    or e.get('slate_date')!=day.isoformat() or obs is None or obs>capture
                    or obs.tz_convert('America/New_York').date()!=day):
                    count['invalid_provenance']+=1
                    continue
                if e.get('published_at') is None:
                    count['publication_unknown']+=1
                    continue
                if pub is None or pub>obs:
                    count['invalid_provenance']+=1
                    continue
                if pub<capture-pd.Timedelta(hours=6):
                    count['stale']+=1
                    continue
                key=(r.team,r.game)
                if key in invalid or (key in latest_news and pub<latest_news[key]):
                    count['news_or_evidence_hold']+=1
                    continue
                count['dated_fresh']+=1
                if (r.verified_outcome!='played' or not isinstance(r.nba_source,str) or not r.nba_source.strip()
                    or bounded(r.actual_minutes,1/60,60) is None):
                    count['outcome_not_played_or_unverified']+=1
                    continue
                contributed=False
                for metric,forecast,actual,daily,reviewed in (
                    ('FD points',bounded(e.get('fd_points'),0,150),bounded(r.actual_points,-150,300),
                     bounded(r.daily_points,0,150),bounded(r.adjusted_fd_points,0,150)),
                    ('Minutes',bounded(e.get('minutes'),0,48),bounded(r.actual_minutes,1/60,60),
                     bounded(r.daily_minutes,0,48),bounded(r.adjusted_minutes,0,48))):
                    if None in (forecast,actual,daily,reviewed):
                        continue
                    contributed=True
                    detail.append(dict(slate_date=day.isoformat(),fanduel_id=r.fanduel_id,provider=provider,
                        metric=metric,published_at=pub.isoformat(),observed_at=obs.isoformat(),
                        forecast=forecast,actual=actual,daily=daily,reviewed=reviewed,
                        source_error=forecast-actual,daily_error=daily-actual,reviewed_error=reviewed-actual))
                if contributed:
                    count['matched_played_players']+=1
                else:
                    count['missing_comparable_metric']+=1
        fields=('archived_players','ambiguous','invalid_provenance','publication_unknown','stale',
                'news_or_evidence_hold','dated_fresh','outcome_not_played_or_unverified',
                'matched_played_players','missing_comparable_metric')
        for p,c in counters.items():
            coverage.append(dict(slate_date=day.isoformat(),provider=p,eligible_players=eligible,
                                 **{k:c[k] for k in fields}))
    details=pd.DataFrame(detail,columns=DETAIL_FIELDS)
    daily=[]
    for (day,p,m),g in details.groupby(['slate_date','provider','metric']):
        daily.append(dict(slate_date=day,provider=p,metric=m,paired_players=len(g),
                          source_mae=g.source_error.abs().mean(),daily_mae=g.daily_error.abs().mean(),
                          reviewed_mae=g.reviewed_error.abs().mean(),source_bias=g.source_error.mean()))
    days=pd.DataFrame(daily)
    aggregate=[]
    if not days.empty:
        for (p,m),g in days.groupby(['provider','metric']):
            aggregate.append(dict(provider=p,metric=m,dates=len(g),paired_players=int(g.paired_players.sum()),
                equal_date_source_mae=g.source_mae.mean(),equal_date_daily_mae=g.daily_mae.mean(),
                equal_date_reviewed_mae=g.reviewed_mae.mean(),equal_date_source_bias=g.source_bias.mean(),
                status='Descriptive reference evidence; not an independent scoring weight'))
    return details,days,pd.DataFrame(aggregate),pd.DataFrame(coverage)
