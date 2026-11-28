import hashlib
import io
import json
from zipfile import ZipFile

import pytest

from nba_archive_replay import MEMBER, verified_observations


def make_zip(value, member=MEMBER):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(member, json.dumps(value))
    return stream.getvalue()


def test_verified_observations_rejects_wrong_digest_and_wrong_shape():
    records = [{"nba_id": "123"}]
    payload = make_zip(records)
    assert verified_observations(payload, archive_sha256=hashlib.sha256(payload).hexdigest()) == records
    with pytest.raises(ValueError, match="SHA-256"):
        verified_observations(payload, archive_sha256="0"*64)
    for bad in ({}, [1]):
        payload = make_zip(bad)
        with pytest.raises(ValueError, match="observation records"):
            verified_observations(payload, archive_sha256=hashlib.sha256(payload).hexdigest())
    missing = make_zip(records, "other.json")
    with pytest.raises(ValueError, match="exactly one"):
        verified_observations(missing, archive_sha256=hashlib.sha256(missing).hexdigest())
