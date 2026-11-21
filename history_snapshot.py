"""Load an immutable SQLite snapshot from a private HTTPS endpoint."""
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from history_backup import inspect
from history_readonly import load_history

MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
HISTORY_REPO_API = 'https://api.github.com/repos/JakeRobes24/dfs-model-2-history'
CHECKPOINT_PATH = re.compile(r'checkpoints/\d{4}-\d{2}-\d{2}-\d{8}T\d{12}Z/history\.sqlite')
SHA256 = re.compile(r'[0-9a-f]{64}')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect could forward the authorization header to a different host.
        return None


def _request(url, token, *, raw=False):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if raw:
        headers['Accept'] = 'application/vnd.github.raw+json'
    return build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=10)


def _read_metadata(url, token, *, raw=False):
    limit = 16 * 1024
    with _request(url, token, raw=raw) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError('History metadata exceeds the size limit')
    return content.decode('utf-8')


def load_latest_snapshot(fallback_url, fallback_sha256, token):
    """Read one immutable history commit, including its pointer, manifest and SQLite bytes."""
    ref = json.loads(_read_metadata(f'{HISTORY_REPO_API}/git/ref/heads/main', token))
    ref_object = ref.get('object') if isinstance(ref, dict) else None
    commit = ref_object.get('sha') if isinstance(ref_object, dict) else None
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid history commit')
    contents = f'{HISTORY_REPO_API}/contents'
    try:
        path = _read_metadata(f'{contents}/latest-history.txt?ref={commit}', token, raw=True).strip()
    except HTTPError as error:
        if error.code != 404:
            raise
        return load_snapshot(fallback_url, fallback_sha256, token)
    if not CHECKPOINT_PATH.fullmatch(path):
        raise ValueError('Invalid history checkpoint path')
    manifest = json.loads(_read_metadata(f'{contents}/{path}.manifest.json?ref={commit}', token, raw=True))
    digest = manifest.get('sha256') if isinstance(manifest, dict) else None
    tables = manifest.get('tables') if isinstance(manifest, dict) else None
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError('Invalid history manifest checksum')
    if not isinstance(tables, dict):
        raise ValueError('Invalid history manifest table counts')
    rows, status = load_snapshot(f'{contents}/{path}?ref={commit}', digest, token, expected_tables=tables)
    return rows, f'{status} Published backup {commit[:7]}.'


def load_snapshot(url, expected_sha256, token='', *, expected_tables=None):
    """Verify all bytes and SQLite integrity before handing off to the read-only loader."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('History snapshot requires an HTTPS URL without user credentials')
    if not SHA256.fullmatch(expected_sha256):
        raise ValueError('History snapshot requires a lowercase SHA-256 digest')

    with TemporaryDirectory(prefix='dfs-history-') as directory:
        path = Path(directory) / 'snapshot.sqlite'
        digest = hashlib.sha256()
        size = 0
        with _request(url, token, raw=parsed.hostname == 'api.github.com') as response, path.open('wb') as destination:
            while chunk := response.read(64 * 1024):
                size += len(chunk)
                if size > MAX_SNAPSHOT_BYTES:
                    raise ValueError('History snapshot exceeds the size limit')
                digest.update(chunk)
                destination.write(chunk)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('History snapshot checksum mismatch')
        tables = inspect(path)
        if expected_tables is not None and tables != expected_tables:
            raise ValueError('History snapshot table counts mismatch')
        return load_history(path)
