import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


def test_real_cli_rejects_an_occupied_port_before_runtime_import(tmp_path):
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        started = time.monotonic()
        result = subprocess.run(
            [
                sys.executable, '-I', '-X', 'importtime',
                str(root / 'ai_host/tests/conformance_cli_entry.py'), str(tmp_path), str(port),
            ],
            cwd=root, capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
        elapsed = time.monotonic() - started
    (tmp_path / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (tmp_path / 'imports.txt').write_text(result.stderr, encoding='utf-8')
    (tmp_path / 'bind-evidence.json').write_text(json.dumps({
        'returncode': result.returncode, 'elapsed_seconds': elapsed, 'port': port,
    }), encoding='utf-8')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'serve bind failed.' in result.stdout
    assert not re.search(r'^import time:.*\|\s+ai_base_runtime(?:\.|\s*$)', result.stderr, flags=re.MULTILINE)
    assert elapsed < 2.0, elapsed
