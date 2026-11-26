"""Submit reviewed slate inputs to the private history automation."""
import base64
import hashlib
import json
import re
from datetime import date
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

import numpy as np
import pandas as pd

from data_integrity import REQUIRED
from history_snapshot import HISTORY_REPO_API, NoRedirect

MAX_PACKET = 8 * 1024 * 1024
CONTEST_PLAYER = re.compile(r'([0-9]{1,12})-[0-9]+')
PRIVATE_API = HISTORY_REPO_API + '/contents/'


def make_submission(pool, slate_date, *, actuals=None, lineups=None):
    if type(slate_date) is not date:
        raise ValueError('Select the slate date.')
    if not REQUIRED.issubset(pool.columns) or pool.empty:
        raise ValueError('Use a complete reconciled pool with authoritative positions.')
    ids = pool.fanduel_id.astype('string')
    parsed = ids.str.extract(CONTEST_PLAYER.pattern + r'\Z', expand=False)
    if ids.isna().any() or not ids.str.fullmatch(CONTEST_PLAYER).fillna(False).all() or ids.duplicated().any():
        raise ValueError('Use unique, complete FanDuel player IDs.')
    if parsed.nunique() != 1:
        raise ValueError('Save one contest at a time.')
    salary = pd.to_numeric(pool.salary, errors='coerce')
    if not salary.between(1, 60000).all() or pool.position.isna().any():
        raise ValueError('Use valid salaries and authoritative positions.')
    contest = str(parsed.iloc[0])
    record = {
        'version': 1, 'slate_date': slate_date.isoformat(), 'contest_id': contest,
        'research_csv': pool.to_csv(index=False, lineterminator='\n'),
    }
    if actuals is not None:
        actual = _csv(actuals)
        _validate_ids(actual, ids, 'Actuals')
        fields = {'actual_minutes', 'actual_fd_points', 'actuals_source'}
        if actual.empty or not fields.issubset(actual.columns) or actual.fanduel_id.duplicated().any():
            raise ValueError('Actuals require unique player IDs, minutes, FanDuel points and a source.')
        for col in ('actual_minutes', 'actual_fd_points'):
            supplied = actual[col].notna()
            values = pd.to_numeric(actual.loc[supplied, col], errors='coerce')
            if values.isna().any() or not np.isfinite(values).all() or (col == 'actual_minutes' and not values.ge(0).all()):
                raise ValueError('Actuals contain invalid numeric values.')
        recorded = actual[['actual_minutes', 'actual_fd_points']].notna().any(axis=1)
        if not recorded.any() or not actual.loc[recorded, 'actuals_source'].fillna('').str.strip().ne('').all():
            raise ValueError('Include the verified source for every recorded result.')
        record['actuals_csv'] = actuals
    if lineups is not None:
        entries = _csv(lineups)
        _validate_ids(entries, ids, 'Lineups')
        if entries.empty or not {'lineup', 'slot'}.issubset(entries.columns):
            raise ValueError('Final lineups require the lineup and slot columns.')
        record['lineups_csv'] = lineups
    raw = (json.dumps(record, sort_keys=True, ensure_ascii=False) + '\n').encode()
    if len(raw) > MAX_PACKET:
        raise ValueError('This archive is larger than 8 MiB.')
    return f'incoming-app/{slate_date}/{contest}/{hashlib.sha256(raw).hexdigest()}.json', raw


def _csv(text):
    try:
        return pd.read_csv(StringIO(text), dtype='string')
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError('Use a valid CSV file.') from exc


def _validate_ids(frame, ids, label):
    if 'fanduel_id' not in frame or frame.fanduel_id.isna().any() or not frame.fanduel_id.isin(ids).all():
        raise ValueError(f'{label} must use player IDs from this contest.')


def submit_reviewed_slate(token, path, raw):
    """Create one immutable packet and handle duplicate clicks or uncertain retries."""
    prefix = r'incoming-app/[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{1,12}/'
    digest = hashlib.sha256(raw).hexdigest()
    if not token or len(raw) > MAX_PACKET or re.fullmatch(prefix + digest + r'\.json', path) is None:
        raise ValueError('Invalid history submission.')
    opener = build_opener(NoRedirect())
    url = PRIVATE_API + path
    headers = {
        'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
    }
    payload = json.dumps({
        'message': 'Archive reviewed DFS slate from Streamlit',
        'content': base64.b64encode(raw).decode('ascii'), 'branch': 'main',
    }).encode()
    try:
        with opener.open(Request(url, payload, headers, method='PUT'), timeout=15) as response:
            result = json.load(response)
            commit = result.get('commit', {}).get('sha')
            if response.status != 201 or not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
                raise OSError('GitHub did not confirm a new submission.')
            return commit[:7]
    except HTTPError as error:
        if error.code not in (409, 422):
            raise OSError('The private archive rejected the submission.') from error
    except (URLError, TimeoutError):
        pass
    read_headers = dict(headers, Accept='application/vnd.github.raw+json')
    try:
        with opener.open(Request(url + '?ref=main', headers=read_headers), timeout=15) as response:
            if response.read(len(raw) + 1) == raw:
                return None
    except (URLError, TimeoutError):
        pass
    raise OSError('The private archive did not confirm the save. Retry with the same inputs.')


def list_slate_packets(token, slate_date, contest):
    """Pin the archive to one commit and list immutable inputs for an exact contest."""
    from history_snapshot import history_head, _request

    if type(slate_date) is not date or re.fullmatch(r'[0-9]{1,12}', contest) is None:
        raise ValueError('Select a valid date and contest ID.')
    commit = history_head(token)
    folder = f'incoming-app/{slate_date}/{contest}'
    try:
        with _request(f'{PRIVATE_API}{folder}?ref={commit}', token) as response:
            content = response.read(MAX_PACKET + 1)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        return commit, folder, []
    if len(content) > MAX_PACKET:
        raise ValueError('Slate archive listing exceeds the size limit.')
    records = json.loads(content)
    if not isinstance(records, list) or len(records) >= 1000:
        raise ValueError('Slate archive listing could not be verified.')
    versions = [entry['name'] for entry in records if entry.get('type') == 'file'
                and re.fullmatch(r'[0-9a-f]{64}\.json', entry.get('name', ''))]
    return commit, folder, sorted(versions)


def load_slate_packet(token, commit, folder, filename):
    """Verify the bytes using the archive's content-addressed filename."""
    from history_snapshot import _request

    if (not re.fullmatch(r'[0-9a-f]{40}', commit)
            or not re.fullmatch(r'incoming-app/\d{4}-\d{2}-\d{2}/\d{1,12}', folder)
            or not re.fullmatch(r'[0-9a-f]{64}\.json', filename)):
        raise ValueError('Invalid slate archive reference.')
    with _request(f'{PRIVATE_API}{folder}/{filename}?ref={commit}', token, raw=True) as response:
        data = response.read(MAX_PACKET + 1)
    if len(data) > MAX_PACKET or hashlib.sha256(data).hexdigest() != filename[:-5]:
        raise ValueError('Saved slate checksum mismatch.')
    record = json.loads(data)
    _, slate, contest = folder.split('/')
    if record.get('version') != 1 or record.get('slate_date') != slate or record.get('contest_id') != contest:
        raise ValueError('Saved slate metadata mismatch.')
    pool = _csv(record['research_csv'])
    required = {'fanduel_id', 'fanduel_name', 'game', 'team', 'adjusted_fd_points'}
    if (pool.empty or not required <= set(pool) or pool.fanduel_id.duplicated().any()
            or not pool.fanduel_id.str.fullmatch(fr'{contest}-\d+').fillna(False).all()):
        raise ValueError('Saved slate does not contain a verified contest pool.')
    return pool, _csv(record['lineups_csv']) if record.get('lineups_csv') else None


def recovery_packet_path(raw):
    """Identify exact downloaded bytes, without trusting any claimed replay timing."""
    if not isinstance(raw, bytes) or not raw or len(raw)>MAX_PACKET:
        raise ValueError('Use a nonempty archive packet smaller than 8 MiB.')
    try:
        record=json.loads(raw)
    except (UnicodeDecodeError,ValueError) as exc:
        raise ValueError('Invalid archive packet JSON.') from exc
    if not isinstance(record,dict) or record.get('version')!=1:
        raise ValueError('Unsupported archive packet version.')
    slate,contest=record.get('slate_date'),record.get('contest_id')
    if (not isinstance(slate,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',slate)
            or not isinstance(contest,str) or not re.fullmatch(r'\d{1,12}',contest)):
        raise ValueError('Invalid archive date or contest ID.')
    date.fromisoformat(slate)
    if not isinstance(record.get('research_csv'),str) or not record['research_csv'].strip():
        raise ValueError('Packet has no reviewed pool.')
    return f'incoming-app/{slate}/{contest}/{hashlib.sha256(raw).hexdigest()}.json'


def check_recovery_receipt(token, raw):
    """Read-only exact-byte receipt at a pinned main commit; no upload or backup claim."""
    from history_snapshot import history_head, _request
    if not token:
        raise ValueError('A history read credential is required.')
    path=recovery_packet_path(raw)
    commit=history_head(token)
    try:
        with _request(f'{PRIVATE_API}{path}?ref={commit}',token,raw=True) as response:
            saved=response.read(len(raw)+1)
    except HTTPError as exc:
        if exc.code==404:
            return dict(path=path,commit=commit,status='not_found')
        raise
    if saved!=raw:
        raise ValueError('Remote archive bytes do not match the local packet.')
    return dict(path=path,commit=commit,status='verified')
