"""Portable, read-only archive of an NFL staging candidate review."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from nfl_daily_audit import raw_bytes
from nfl_projection_review import stamp
from nfl_reviewed_candidates import compare_reviewed_nfl

BUNDLE_FIELDS = ('slate_date', 'cutoff_utc', 'daily_capture', 'evidence', 'candidates', 'salary_cap')
LIMITS = {'contest.csv': 8 * 2**20, 'daily.csv': 8 * 2**20,
          'review_bundle.json': 4 * 2**20, 'report.json': 8 * 2**20, 'manifest.json': 4096}


def review_bundle(raw):
    if not isinstance(raw, bytes) or len(raw) > LIMITS['review_bundle.json']:
        raise ValueError('Expected a candidate JSON file within the archive size limit.')
    bundle = json.loads(raw)
    if not isinstance(bundle, dict) or set(BUNDLE_FIELDS) - bundle.keys():
        raise ValueError('Candidate bundle is missing required review inputs.')
    return {key: bundle[key] for key in BUNDLE_FIELDS}


def _json(value):
    return json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode('utf-8') + b'\n'


def _digest(raw):
    return sha256(raw).hexdigest()


def _manifest_metadata(bundle, report, captured_at, single_game):
    captured = stamp(captured_at).astimezone(timezone.utc)
    cutoff = stamp(report['cutoff_utc'])
    known_times = [bundle['daily_capture']['observed_at']]
    known_times.extend(player['asof_utc'] for player in report['accepted_players'])
    known_times.extend(
        source['observed_at']
        for player in report['source_review']['rows']
        for source in player['accepted_source_records']
    )
    # Candidate times were validated when ranking was possible.
    if report['ready']:
        known_times.extend(candidate['created_utc'] for candidate in bundle['candidates'])
    if captured >= cutoff:
        timing = 'at_or_after_declared_cutoff'
    elif any(stamp(value) > captured for value in known_times):
        timing = 'claimed_inputs_after_capture'
    else:
        timing = 'before_declared_cutoff'
    return {
        'schema': 1, 'contest_id': report['contest_id'], 'single_game': single_game,
        'slate_date': report['slate_date'], 'cutoff_utc': report['cutoff_utc'],
        'captured_at_utc': captured.isoformat(), 'timing': timing,
    }


def create_nfl_review_archive(contest_raw, daily_raw, bundle_raw, *, contest_id,
                              single_game, captured_at=None):
    """Freeze the original inputs and regenerate the reviewed result from them."""
    if type(single_game) is not bool:
        raise ValueError('A Classic or Single game contest format is required.')
    contest_raw, daily_raw = raw_bytes(contest_raw), raw_bytes(daily_raw)
    bundle = review_bundle(bundle_raw)
    report = compare_reviewed_nfl(contest_raw, daily_raw, contest_id=contest_id,
                                  single_game=single_game, **bundle)
    capture = captured_at if captured_at is not None else datetime.now(timezone.utc).isoformat()
    manifest = _manifest_metadata(bundle, report, capture, single_game)
    files = {'contest.csv': contest_raw, 'daily.csv': daily_raw,
             'review_bundle.json': bundle_raw, 'report.json': _json(report)}
    if any(len(payload) > LIMITS[name] for name, payload in files.items()):
        raise ValueError('NFL review archive member exceeds its size limit.')
    manifest['sha256'] = {name: _digest(payload) for name, payload in files.items()}
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
        archive.writestr('manifest.json', _json(manifest))
    return output.getvalue(), manifest


def restore_nfl_review_archive(raw):
    """Check archive integrity and compare a current replay with the saved result."""
    if not isinstance(raw, bytes) or len(raw) > sum(LIMITS.values()) + 65536:
        raise ValueError('NFL review ZIP exceeds its size limit.')
    try:
        with ZipFile(BytesIO(raw)) as archive:
            members = archive.infolist()
            if (len(members) != len(LIMITS) or {item.filename for item in members} != LIMITS.keys()
                    or any(item.file_size > LIMITS[item.filename] or item.flag_bits & 1 for item in members)):
                raise ValueError('Unexpected, duplicate or oversized NFL review ZIP member.')
            files = {item.filename: archive.read(item) for item in members}
    except (BadZipFile, NotImplementedError, RuntimeError, EOFError) as error:
        raise ValueError('Invalid NFL review ZIP.') from error

    manifest = json.loads(files.pop('manifest.json'))
    if (not isinstance(manifest, dict) or manifest.get('schema') != 1
            or type(manifest.get('single_game')) is not bool
            or manifest.get('sha256') != {name: _digest(raw) for name, raw in files.items()}):
        raise ValueError('NFL review archive manifest or member checksum mismatch.')

    expected_report = json.loads(files['report.json'])
    bundle = review_bundle(files['review_bundle.json'])
    current_report = compare_reviewed_nfl(files['contest.csv'], files['daily.csv'],
                                          contest_id=manifest.get('contest_id'),
                                          single_game=manifest['single_game'], **bundle)
    if (not isinstance(expected_report, dict)
            or expected_report.get('contest_sha256') != manifest['sha256']['contest.csv']
            or expected_report.get('daily_sha256') != manifest['sha256']['daily.csv']):
        raise ValueError('Recorded review does not reference the original inputs.')
    details = _manifest_metadata(bundle, expected_report, manifest.get('captured_at_utc'),
                                 manifest['single_game'])
    if {**details, 'sha256': manifest['sha256']} != manifest:
        raise ValueError('NFL review manifest disagrees with the recorded review.')
    return manifest, expected_report, current_report == expected_report
