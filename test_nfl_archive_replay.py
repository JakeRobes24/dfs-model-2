import hashlib
import io
from zipfile import ZipFile

import pytest

from nfl_archive_replay import MEMBER, verified_workload


def test_archive_replay_verifies_both_hashes_and_part_order():
    csv = b"gsis_id,pfr_id,week\n00-001,Test00,1\n"
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(MEMBER, csv)
    data = stream.getvalue()
    parts = [data[:30], data[30:]]
    args = dict(archive_sha256=hashlib.sha256(data).hexdigest(),
                workload_sha256=hashlib.sha256(csv).hexdigest())
    assert verified_workload(parts, **args).gsis_id.tolist() == ["00-001"]
    with pytest.raises(ValueError, match="Archive SHA-256"):
        verified_workload(parts[::-1], **args)
    with pytest.raises(ValueError, match="Workload CSV SHA-256"):
        verified_workload(parts, **dict(args, workload_sha256="0"*64))


def test_archive_replay_rejects_duplicate_workload_member():
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(MEMBER, b"first")
        with pytest.warns(UserWarning):
            archive.writestr(MEMBER, b"second")
    data = stream.getvalue()
    with pytest.raises(ValueError, match="exactly one"):
        verified_workload([data], archive_sha256=hashlib.sha256(data).hexdigest())
