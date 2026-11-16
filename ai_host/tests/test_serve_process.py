import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def test_real_serve_stops_project_and_runtime_without_leaving_its_listener(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source_paths = (
        'ai_host/management/commands/serve.py', 'ai_host/lifecycle.py', 'ai_host/state.py',
        'ai_host/runtime_artifact.json', 'project_management/runtime.py',
        'project_management/app/api/run_factories.py', 'ai_host/tests/serve_test_entry.py',
        'ai_host/tests/test_serve_process.py', 'scripts/validation/run_report_authoring_tests.py',
    )

    def fingerprints():
        return {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in source_paths}

    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    stop_file = tmp_path / 'stop.flag'
    log_file = tmp_path / 'serve.log'
    evidence = {'port': port, 'source_before': fingerprints(), 'responses': {}, 'forced_cleanup': False}
    command = [
        sys.executable, '-I', str(root / 'ai_host/tests/serve_test_entry.py'),
        str(tmp_path), str(port), str(stop_file),
    ]
    with log_file.open('wb') as log:
        process = subprocess.Popen(
            command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
        evidence['pid'] = process.pid
        try:
            deadline = time.monotonic() + 40
            while True:
                assert process.poll() is None, log_file.read_text(encoding='utf-8', errors='replace')
                try:
                    with opener.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                        assert response.status == 200
                        evidence['responses']['/'] = response.status
                        break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline, log_file.read_text(encoding='utf-8', errors='replace')
                    time.sleep(0.1)
            with opener.open(f'http://127.0.0.1:{port}/ai/', timeout=3) as response:
                evidence['responses']['/ai/'] = response.status
                html = response.read().decode('utf-8')
            assets = sorted(set(re.findall(r'(/ai/assets/[^"\']+\.(?:js|css))', html)))
            assert assets
            for asset in assets:
                with opener.open(f'http://127.0.0.1:{port}{asset}', timeout=3) as response:
                    evidence['responses'][asset] = response.status
                    assert response.status == 200
                    assert response.read()
            stopped_at = time.monotonic()
            stop_file.write_text('stop\n', encoding='utf-8')
            evidence['returncode'] = process.wait(timeout=15)
            evidence['stop_seconds'] = time.monotonic() - stopped_at
        finally:
            if process.poll() is None:
                stop_file.write_text('stop\n', encoding='utf-8')
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    evidence['forced_cleanup'] = True
                    process.kill()
                    process.wait(timeout=5)
            evidence['source_after'] = fingerprints()
            evidence['returncode'] = process.returncode
            (tmp_path / 'serve-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    output = log_file.read_text(encoding='utf-8', errors='replace')
    assert process.returncode == 0, output
    assert 'Traceback (most recent call last)' not in output
    assert not evidence['forced_cleanup']
    assert evidence['source_before'] == evidence['source_after']
    events = [json.loads(line) for line in output.splitlines() if line.startswith('{"schema_version"')]
    stopped = next(event for event in events if event.get('event') == 'project_runtime_stopped')
    assert stopped['stopped'] is True and stopped['unresolved'] == []
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(('127.0.0.1', port)) != 0
    assert not tuple((tmp_path / 'tmp_ui_validation').iterdir())
