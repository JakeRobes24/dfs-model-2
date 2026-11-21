"""Static staging checks; no live Streamlit process or deployment."""
from pathlib import Path

def test_staged_app():
    root=Path(__file__).parent
    app=(root/'app_staging.py').read_text()
    original=(root/'app.py').read_text()
    assert app.startswith('from history_panel import render_history_panel\n')
    assert 'render_history_panel()' in app
    assert original in app
    assert 'def render_history_panel' in (root/'history_panel.py').read_text()
    assert 'mode=ro' in (root/'history_readonly.py').read_text()
if __name__=='__main__':
    test_staged_app();print('Staged app static checks passed')
