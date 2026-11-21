from pathlib import Path
import subprocess
import sys


def test_runtime_smoke_reports_blocked_when_streamlit_missing():
    root = Path(__file__).resolve().parent
    proc = subprocess.run([sys.executable, str(root / 'streamlit_runtime_smoke.py')], capture_output=True, text=True)
    if 'BLOCKED: Streamlit is not installed' in proc.stdout:
        assert proc.returncode == 2
    else:
        assert proc.returncode == 0, proc.stdout + proc.stderr
