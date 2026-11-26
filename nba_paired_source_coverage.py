"""Read-only audit of saved point/minute coverage by independent source family.

This is a coverage inventory, not an acceptance decision or a projection model.
Missing archived records cannot distinguish fetch failure from an unattempted
source, a stale estimate, or an unsuccessful player match.
"""
import json
import math
from collections import Counter
import pandas as pd
from nba_distribution_review import timestamp, bounded
from slate_research import POINT_SOURCE_GROUPS

def paired_source_coverage(frame):
    required={"fanduel_id","eligible","projection_sources_json","replay_captured_at_utc"}
    if not required<=set(frame) or not frame.fanduel_id.is_unique or frame.fanduel_id.isna().any():
        raise ValueError("Unique archived full-pool player rows required")
    captures=[timestamp(v) for v in frame.replay_captured_at_utc]
    if not captures or any(v is None for v in captures) or len(set(captures))!=1:
        raise ValueError("One timezone-aware archived capture required")
    capture=captures[0]
    families=sorted(set(POINT_SOURCE_GROUPS.values()))
    counts={family:Counter() for family in families}
    buckets=Counter()
    malformed=0
    eligible=0
    for row in frame.itertuples(index=False):
        if str(row.eligible).lower()!="true":
            continue
        eligible+=1
        by_family={}
        try:
            records=json.loads(row.projection_sources_json)
            if not isinstance(records,list):
                raise ValueError
        except (ValueError,TypeError):
            malformed+=1
            buckets["unreadable"]+=1
            continue
        for record in records:
            if not isinstance(record,dict):
                malformed+=1
                continue
            family=POINT_SOURCE_GROUPS.get(record.get("source"))
            if family is None or record.get("family")!=family:
                malformed+=1
                continue
            by_family.setdefault(family,[]).append(record)
        pairs=0
        for family,notes in by_family.items():
            c=counts[family]
            c["recorded_players"]+=1
            # A saved consensus should contain at most one accepted record for
            # a family. Never treat ambiguous duplicates as corroboration.
            if len(notes)!=1:
                c["ambiguous_players"]+=1
                continue
            note=notes[0]
            stamp=timestamp(note.get("observed_at"))
            points=bounded(note.get("points"),0,150)
            minutes=bounded(note.get("paired_minutes"),0,60)
            if stamp is None or not capture-pd.Timedelta(hours=6)<=stamp<=capture or points is None:
                c["invalid_or_stale_players"]+=1
                continue
            c["fresh_points_players"]+=1
            if minutes is not None and minutes>0:
                c["fresh_paired_players"]+=1
                pairs+=1
            else:
                c["points_without_positive_minutes"]+=1
        buckets["two_or_more_pairs" if pairs>=2 else "one_pair" if pairs==1 else "no_pairs"]+=1
    fields=("recorded_players","fresh_points_players","fresh_paired_players",
            "points_without_positive_minutes","ambiguous_players","invalid_or_stale_players")
    sources=[dict(family=f,**{k:counts[f][k] for k in fields},
                  missing_archived_players=eligible-counts[f]["recorded_players"]) for f in families]
    return {"eligible_players":eligible,"capture_utc":capture.isoformat(),"sources":sources,
            "player_pair_coverage":dict(buckets),"malformed_records_or_payloads":malformed,
            "certified":False,
            "warning":"Archived coverage only; source absence is not a verified fetch failure. Positive paired fields do not establish role, independence, or live scoring eligibility."}
