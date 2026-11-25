"""Session-local retention of a reconciled pair of uploaded slate files."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SlateUpload:
    name: str
    data: bytes


def select_upload_pair(contest, daily, retained):
    """Return (pair, recovered). Never combine a new file with a retained partner."""
    if contest is not None and daily is not None:
        if not contest.data or not daily.data:
            return None, False
        return (contest, daily), False
    if retained is None:
        return None, False
    for incoming, original in zip((contest,daily),retained):
        if incoming is not None and incoming != original:
            return None, False
    return retained, True
