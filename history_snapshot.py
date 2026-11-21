"""Load an immutable SQLite snapshot from a private HTTPS endpoint."""
import hashlib
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from history_backup import inspect
from history_readonly import load_history

MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect could forward the authorization header to a different host.
        return None


def load_snapshot(url, expected_sha256, token=''):
    """Verify all bytes and SQLite integrity before handing off to the read-only loader."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('History snapshot requires an HTTPS URL without user credentials')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('History snapshot requires a lowercase SHA-256 digest')

    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if parsed.hostname == 'api.github.com':
        headers['Accept'] = 'application/vnd.github.raw+json'
    request = Request(url, headers=headers)
    opener = build_opener(NoRedirect())
    with TemporaryDirectory(prefix='dfs-history-') as directory:
        path = Path(directory) / 'snapshot.sqlite'
        digest = hashlib.sha256()
        size = 0
        with opener.open(request, timeout=10) as response, path.open('wb') as destination:
            while chunk := response.read(64 * 1024):
                size += len(chunk)
                if size > MAX_SNAPSHOT_BYTES:
                    raise ValueError('History snapshot exceeds the size limit')
                digest.update(chunk)
                destination.write(chunk)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('History snapshot checksum mismatch')
        inspect(path)
        return load_history(path)
