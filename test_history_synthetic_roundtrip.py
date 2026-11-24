"""Exercise real SQLite backup/readback with synthetic data and mocked HTTPS.

No private database, credential, or live request is needed.
"""
from io import BytesIO
import json
from unittest.mock import patch

import pandas as pd
import pytest

from history_backup import backup, sha256, verify_backup
from history_snapshot import HISTORY_REPO_API, load_latest_snapshot
from player_store import connect, import_snapshot, import_actuals


def test_immutable_backup_roundtrip(tmp_path):
    day='2026-11-24'
    source=tmp_path/'source.sqlite'
    research=tmp_path/'research.csv'
    actuals=tmp_path/'actuals.csv'
    pd.DataFrame({'fanduel_id':['123-1','123-2'],'fanduel_name':['Fixture A','Fixture B'],
        'salary':[6000,7000],'position':['PG','C'],'roster_eligibility':['PG/G/F/UTIL','C/F/C/UTIL'],
        'adjusted_fd_points':[33.5,41.2],'projected_minutes':[30,32],
        'adjusted_minutes':[31,32]}).to_csv(research,index=False)
    pd.DataFrame({'fanduel_id':['123-1'],'actual_minutes':[30],'actual_fd_points':[35.7],
                  'actuals_source':['Synthetic test only']}).to_csv(actuals,index=False)
    db=connect(source)
    try:
        assert import_snapshot(db,research,day)['status']=='imported'
        assert import_actuals(db,actuals,day)['recorded']==1
        assert import_snapshot(db,research,day)['status']=='already_imported'
        assert import_actuals(db,actuals,day)['unchanged']==1
    finally:
        db.close()
    original=sha256(source)
    snapshot=tmp_path/'history.sqlite'
    manifest=backup(source,snapshot)
    assert verify_backup(snapshot)==manifest
    commit='a'*40
    checkpoint='checkpoints/2026-11-24-20261124T200000000000Z/history.sqlite'
    def responses(m,blob):
        return [BytesIO(json.dumps({'object':{'sha':commit}}).encode()),
                BytesIO(checkpoint.encode()),BytesIO(json.dumps(m).encode()),BytesIO(blob)]
    with patch('history_snapshot.build_opener') as opener:
        opener.return_value.open.side_effect=responses(manifest,snapshot.read_bytes())
        loaded,status=load_latest_snapshot('https://example.org/fallback',manifest['sha256'],'fixture-only')
        assert len(loaded)==2 and loaded.actual_fd_points.notna().sum()==1
        assert loaded.loc[loaded.fanduel_id.eq('123-1'),'actual_fd_points'].iloc[0]==pytest.approx(35.7)
        assert 'Published backup aaaaaaa' in status
        request=opener.return_value.open.call_args.args[0]
        assert request.full_url==f'{HISTORY_REPO_API}/contents/{checkpoint}?ref={commit}'
        assert request.get_header('Authorization')=='Bearer fixture-only'
        assert sha256(source)==original
        opener.return_value.open.side_effect=responses(manifest,snapshot.read_bytes()+b'corruption')
        with pytest.raises(ValueError,match='checksum mismatch'):
            load_latest_snapshot('https://example.org/fallback',manifest['sha256'],'fixture-only')
        wrong=dict(manifest,tables=dict(manifest['tables'],actuals=2))
        opener.return_value.open.side_effect=responses(wrong,snapshot.read_bytes())
        with pytest.raises(ValueError,match='table counts mismatch'):
            load_latest_snapshot('https://example.org/fallback',manifest['sha256'],'fixture-only')
