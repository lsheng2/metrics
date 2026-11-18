import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

import pytest

from ai_host.tests.conformance_runtime_probe import AssetParser
from scripts.validation.project_full_stack_support import base_environment


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / 'ai_host/tests/windows_perf_entry.py'


@pytest.mark.parametrize('production', [False, True])
def test_baseline_and_real_host_share_seed_pages_assets_and_idle_worker(tmp_path, production):
    marker = {'owner': 'windows-host-qualification', 'root': str(tmp_path.resolve())}
    (tmp_path / 'owner.json').write_text(json.dumps(marker), encoding='utf-8')
    seed = subprocess.run(
        [sys.executable, '-I', str(ENTRY), 'seed', '--root', str(tmp_path)],
        capture_output=True, text=True, timeout=60, env=base_environment(tmp_path / 'seed-env'),
    )
    assert seed.returncode == 0, seed.stdout + seed.stderr
    processes, logs, ports = {}, {}, {}
    opener = build_opener(ProxyHandler({}))
    auth = 'Basic ' + base64.b64encode(b'alice:wonder').decode()
    observations = {}
    try:
        for role in ('baseline', 'candidate'):
            instance = tmp_path / role
            instance.mkdir()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            ports[role] = port
            log = (instance / 'process.log').open('wb')
            logs[role] = log
            processes[role] = subprocess.Popen(
                [sys.executable, '-I', str(ENTRY), 'serve', '--root', str(tmp_path),
                 '--instance', str(instance), '--role', role, '--port', str(port),
                 *(['--production'] if production else [])],
                stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
                env=base_environment(instance / 'environment'),
            )
        for role, process in processes.items():
            deadline = time.monotonic() + 45
            while True:
                assert process.poll() is None, (tmp_path / role / 'process.log').read_text(encoding='utf-8')
                try:
                    with opener.open(Request(
                        f'http://127.0.0.1:{ports[role]}/qualification/pages/', headers={'Authorization': auth},
                    ), timeout=2) as response:
                        observations[role] = json.loads(response.read())
                    break
                except (URLError, TimeoutError):
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
            assert observations[role]['worker_started']
            assert observations[role]['worker_executed'] == []
            assert observations[role]['debug'] is not production
            if production:
                assert observations[role]['collected_static_files'] > 0
            assert set(observations[role]['pages']) == {
                'home', 'projects', 'project_detail', 'stage_reports', 'draft_edit', 'bug_trend',
            }
            observations[role]['assets'] = {}
            observations[role]['asset_hashes'] = {}
            for key, page in observations[role]['pages'].items():
                with opener.open(Request(
                    f'http://127.0.0.1:{ports[role]}{page}', headers={'Authorization': auth},
                ), timeout=5) as response:
                    assert response.status == 200, key
                    parser = AssetParser('/static/')
                    parser.feed(response.read().decode())
                assert parser.assets, key
                observations[role]['assets'][key] = parser.assets
                for asset in parser.assets:
                    if asset in observations[role]['asset_hashes']:
                        continue
                    with opener.open(Request(
                        f'http://127.0.0.1:{ports[role]}{asset}', headers={'Authorization': auth},
                    ), timeout=5) as response:
                        assert response.status == 200, asset
                        observations[role]['asset_hashes'][asset] = hashlib.sha256(response.read()).hexdigest()
            asset = observations[role]['assets']['home'][0]
            try:
                with opener.open(f'http://127.0.0.1:{ports[role]}{asset}', timeout=3) as response:
                    assert role == 'baseline' and response.status == 200
            except URLError as error:
                assert role == 'candidate' and getattr(error, 'code', None) == 401
        assert observations['baseline']['assets'] == observations['candidate']['assets']
        assert observations['baseline']['asset_hashes'] == observations['candidate']['asset_hashes']
    finally:
        cleanups = {}
        for role in processes:
            (tmp_path / role / 'stop').write_text('stop', encoding='utf-8')
        for role, process in processes.items():
            forced = False
            try:
                code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                forced = True
                process.kill()
                code = process.wait(timeout=3)
            finally:
                logs[role].close()
            with socket.socket() as probe:
                released = probe.connect_ex(('127.0.0.1', ports[role])) != 0
            cleanups[role] = {'code': code, 'forced': forced, 'port_released': released}
        (tmp_path / 'cleanup.json').write_text(json.dumps(cleanups, indent=2), encoding='utf-8')
        assert all(row['code'] == 0 and not row['forced'] and row['port_released'] for row in cleanups.values()), cleanups
    (tmp_path / 'equivalence.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')


def test_native_runner_uses_owned_profiles_and_observed_normal_exit(tmp_path):
    from scripts.validation.windows_host_processes import running_arms
    from scripts.validation.windows_host_samples import client

    with running_arms(tmp_path, Path(sys.executable), production=False, names=('baseline', 'candidate')) as arms:
        with client() as http:
            for name, base in arms.bases.items():
                metadata = arms.record['arms'][name]['metadata']
                assert metadata['worker_started'] and metadata['worker_executed'] == []
                assert http.get(base + metadata['pages']['home']).status_code == 200
    assert arms.record['cleanup']['normal'] is True
    assert all(row['exit_code'] == 0 for row in arms.record['cleanup']['services'].values())
