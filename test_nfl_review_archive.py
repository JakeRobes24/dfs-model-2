from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from nfl_review_archive import create_nfl_review_archive, restore_nfl_review_archive
from test_nfl_reviewed_candidates import fixture


def make_archive(single=False, *, capture='2026-11-26T16:30:00Z', blocked=False, future=False):
    contest, daily, kwargs = fixture(single)
    contest_id = kwargs.pop('contest_id')
    kwargs.pop('single_game')
    kwargs['cutoff_utc'] = '2026-11-26T17:00:00Z'
    if blocked:
        kwargs['evidence'] = []
    if future:
        kwargs['candidates'][0]['created_utc'] = '2026-11-26T16:45:00Z'
    bundle = json.dumps(kwargs).encode('utf-8')
    raw, manifest = create_nfl_review_archive(contest, daily, bundle, contest_id=contest_id,
                                              single_game=single, captured_at=capture)
    return raw, manifest, (contest, daily, bundle)


@pytest.mark.parametrize('single', [False, True])
def test_replay_preserves_original_bytes_candidate_and_timing(single):
    raw, manifest, originals = make_archive(single)
    assert manifest['timing'] == 'before_declared_cutoff'
    with ZipFile(BytesIO(raw)) as archive:
        assert originals == tuple(archive.read(name) for name in ('contest.csv', 'daily.csv', 'review_bundle.json'))
    actual_manifest, report, matches = restore_nfl_review_archive(raw)
    assert matches and actual_manifest == manifest
    assert report['ready'] and not report['certified']
    assert report['rankings'][0]['projected_fd'] == (65 if single else 90)


def test_preserved_incomplete_review_has_no_rankings():
    raw, _, _ = make_archive(blocked=True)
    _, report, matches = restore_nfl_review_archive(raw)
    assert matches and not report['ready']
    assert report['unresolved'] and not report['rankings']


def test_future_inputs_and_exact_cutoff_are_distinguished():
    _, future, _ = make_archive(future=True)
    _, last, _ = make_archive(capture='2026-11-26T17:00:00Z')
    assert future['timing'] == 'claimed_inputs_after_capture'
    assert last['timing'] == 'at_or_after_declared_cutoff'


def test_changed_archive_member_fails_digest():
    raw, _, _ = make_archive()
    edited = BytesIO()
    with ZipFile(BytesIO(raw)) as source, ZipFile(edited, 'w') as target:
        for name in source.namelist():
            target.writestr(name, source.read(name) + (b' ' if name == 'daily.csv' else b''))
    with pytest.raises(ValueError, match='checksum'):
        restore_nfl_review_archive(edited.getvalue())


def test_malformed_container_fails_closed():
    with pytest.raises(ValueError, match='Invalid NFL review ZIP'):
        restore_nfl_review_archive(b'not a ZIP')
