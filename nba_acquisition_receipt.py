"""Read-only archive receipt for actual public research acquisition attempts."""
import json
from collections import Counter
from datetime import date
from nba_distribution_review import timestamp

def acquisition_receipt(slate, checked_at, source_status, notes, projections):
    """Save observed outcomes, not assumptions about missing providers.

    Review cutoff may be reused from cache. Provider publication timestamps
    remain on individual source records; this receipt is not a time proof.
    Only public loader records, before identity matching, are counted here.
    """
    stamp=timestamp(checked_at)
    if type(slate) is not date or stamp is None:
        raise ValueError("Dated research review cutoff required")
    labels=[name for name,_ in source_status]
    if len(labels)!=len(set(labels)):
        raise ValueError("Duplicate source acquisition labels")
    note_counts=Counter(r.get("source") for r in notes if isinstance(r,dict) and isinstance(r.get("source"),str))
    point_counts=Counter(r.get("source") for r in projections if isinstance(r,dict) and isinstance(r.get("source"),str))
    return json.dumps(dict(version=1,slate_date=slate.isoformat(),review_cutoff_utc=stamp.isoformat(),
                           status=[dict(label=name,result=str(detail)) for name,detail in source_status],
                           returned_note_rows=dict(note_counts),returned_point_rows=dict(point_counts),
                           warning="Review cutoff, not provider publication time. May use cached retrieval. Counts before contest matching or score acceptance."),sort_keys=True)
