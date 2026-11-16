import base64
import configparser
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
GRAFANA_HOME = Path('C:/Program Files/GrafanaLabs/grafana')
PLUGIN = Path('D:/AIGC/scrum_dashboard/state/grafana/data/plugins/yesoreyeram-infinity-datasource')


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def request_json(url, *, credentials, payload=None):
    token = base64.b64encode(f'{credentials["username"]}:{credentials["password"]}'.encode()).decode()
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': f'Basic {token}', 'Content-Type': 'application/json'},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=10) as response:
        return json.loads(response.read())


def await_ready(process, url, credentials, log_path, *, timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        assert process.poll() is None, log_path.read_text(encoding='utf-8', errors='replace')
        try:
            return request_json(url, credentials=credentials)
        except (urllib.error.URLError, TimeoutError):
            assert time.monotonic() < deadline, log_path.read_text(encoding='utf-8', errors='replace')
            time.sleep(0.1)


def launch(command, log, *, cwd):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GF_')}
    environment.update({'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'})
    info = None
    if sys.platform == 'win32':
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE
    return subprocess.Popen(
        command, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT,
        startupinfo=info,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
    )


@contextmanager
def running_grafana(directory, credentials):
    directory.mkdir()
    executable = GRAFANA_HOME / 'bin/grafana.exe'
    assert executable.is_file() and (PLUGIN / 'plugin.json').is_file()
    for name in ('data', 'logs', 'provisioning', 'plugins'):
        (directory / name).mkdir()
    shutil.copytree(PLUGIN, directory / 'plugins' / PLUGIN.name)
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    config = configparser.ConfigParser()
    config.read_dict({
        'server': {'http_addr': '127.0.0.1', 'http_port': str(port), 'root_url': base + '/'},
        'paths': {name: (directory / name).as_posix() for name in ('data', 'logs', 'provisioning', 'plugins')},
        'security': {'admin_user': credentials['username'], 'admin_password': credentials['password'],
                     'allow_embedding': 'true'},
        'auth.anonymous': {'enabled': 'true', 'org_role': 'Viewer'},
        'analytics': {'reporting_enabled': 'false', 'check_for_updates': 'false',
                      'check_for_plugin_updates': 'false'},
        'plugins': {'preinstall_disabled': 'true', 'preinstall_auto_update': 'false'},
        'unified_alerting': {'enabled': 'false', 'execute_alerts': 'false'},
        'news': {'news_feed_enabled': 'false'},
    })
    config_path = directory / 'grafana.ini'
    with config_path.open('w', encoding='utf-8') as output:
        config.write(output)
    log_path = directory / 'process.log'
    with log_path.open('wb') as log:
        process = launch([str(executable), 'server', '--homepath', str(GRAFANA_HOME),
                          '--config', str(config_path)], log, cwd=directory)
        forced = False
        try:
            health = await_ready(process, base + '/api/health', credentials, log_path)
            yield base, health
        finally:
            if process.poll() is None:
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32' else signal.SIGTERM)
                    process.wait(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    forced = True
                    process.kill()
                    process.wait(timeout=5)
            (directory / 'stop.json').write_text(json.dumps({
                'pid': process.pid, 'returncode': process.returncode, 'forced': forced,
            }), encoding='utf-8')
        with socket.socket() as probe:
            assert probe.connect_ex(('127.0.0.1', port)) != 0


@contextmanager
def running_publication_stack(directory, endpoint):
    credentials = {'username': 'synthetic-publication-reviewer', 'password': secrets.token_urlsafe(24)}
    directory.mkdir(parents=True, exist_ok=True)
    with running_grafana(directory / 'grafana', credentials) as (grafana, health):
        port = free_port()
        base = f'http://127.0.0.1:{port}'
        config_path, stop = directory / 'synthetic.json', directory / 'stop.flag'
        config_path.write_text(json.dumps({
            **credentials, 'model_url': endpoint.model.base_url, 'grafana_url': grafana,
        }), encoding='utf-8')
        log_path = directory / 'dashboard.log'
        with log_path.open('wb') as log:
            process = launch([
                sys.executable, '-I', str(ROOT / 'ai_host/tests/publication_serve_entry.py'),
                str(directory), str(port), str(stop), str(config_path),
            ], log, cwd=ROOT)
            forced = False
            try:
                await_ready(process, base + '/api/ai-publish-history/', credentials, log_path)
                event = next(json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines()
                             if line.startswith('{"event": "publication_fixture"'))
                request_json(grafana + '/api/datasources', credentials=credentials, payload={
                    'name': 'Synthetic Metrics API', 'uid': 'metrics-bug-trend-api',
                    'type': 'yesoreyeram-infinity-datasource', 'access': 'proxy', 'url': base,
                    'basicAuth': True, 'basicAuthUser': credentials['username'],
                    'jsonData': {'allowedHosts': [base], 'auth_method': 'basicAuth'},
                    'secureJsonData': {'basicAuthPassword': credentials['password']},
                })
                yield {'base': base, 'grafana': grafana, 'grafana_health': health,
                       'credentials': credentials, **event}
            finally:
                stop.write_text('stop\n', encoding='utf-8')
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    forced = True
                    process.kill()
                    process.wait(timeout=5)
                (directory / 'dashboard-stop.json').write_text(json.dumps({
                    'pid': process.pid, 'returncode': process.returncode, 'forced': forced,
                }), encoding='utf-8')
            assert process.returncode == 0 and not forced, log_path.read_text(encoding='utf-8', errors='replace')
        with socket.socket() as probe:
            assert probe.connect_ex(('127.0.0.1', port)) != 0
