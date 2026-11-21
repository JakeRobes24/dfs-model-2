"""Offline execution smoke tests using a Streamlit stand-in.

NOT an actual Streamlit browser/server runtime test.
"""
import contextlib
import os
from pathlib import Path
import runpy
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
DB = ROOT.parent / 'nov20_player_history_verified_backup.sqlite'

class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.events=[]
        self.frames=[]
        self.errors=[]
    def __getattr__(self, name):
        if name in {'expander'}:
            return lambda *a, **k: contextlib.nullcontext()
        if name in {'columns'}:
            return lambda n, **k: [self for _ in range(n)]
        if name in {'file_uploader'}:
            return lambda *a, **k: None
        if name in {'button'}:
            return lambda *a, **k: False
        if name in {'checkbox'}:
            return lambda *a, **k: a[1] if len(a)>1 else k.get('value', False)
        if name in {'slider'}:
            return lambda *a, **k: a[3] if len(a)>3 else k.get('value', 7)
        if name in {'text_input'}:
            return lambda *a, **k: k.get('value', '')
        if name == 'dataframe':
            return lambda frame, **k: self.frames.append(frame)
        if name == 'exception':
            return lambda exc: self.errors.append(str(exc))
        if name in {'error'}:
            return lambda msg: self.errors.append(str(msg))
        return lambda *a, **k: self.events.append((name, a))


def run_app(history_path):
    fake=FakeStreamlit()
    with patch.dict(sys.modules, {'streamlit':fake}), patch.dict(os.environ, {'DFS_HISTORY_DB':history_path}):
        with patch.dict(sys.path_importer_cache, {}, clear=False):
            sys.path.insert(0,str(ROOT))
            try:
                for key in ['history_panel']:
                    sys.modules.pop(key,None)
                runpy.run_path(str(ROOT/'app_staging.py'),run_name='__main__')
            finally:
                sys.path.remove(str(ROOT))
                sys.modules.pop('history_panel',None)
    return fake


def test_staged_app_with_real_history():
    assert DB.exists()
    fake=run_app(str(DB))
    assert not fake.errors, fake.errors
    assert any('actual_fd_points' in frame.columns and len(frame)==247 for frame in fake.frames)
    assert any(name=='metric' and args[0]=='Rows with verified actual FD points' and args[1]==17 for name,args in fake.events)


def test_staged_app_with_missing_history():
    fake=run_app(str(ROOT/'absent.sqlite'))
    assert not fake.errors, fake.errors
    assert any(name=='caption' and 'fallback' in args[0].lower() for name,args in fake.events)


def test_staged_app_without_history_configuration():
    fake=run_app('')
    assert not fake.errors, fake.errors
    assert any(name=='info' and 'No persistent history database configured' in args[0] for name,args in fake.events)
