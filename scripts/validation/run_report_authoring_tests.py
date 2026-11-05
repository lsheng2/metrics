import importlib
from contextvars import ContextVar
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
import django
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
LOCAL_HOSTS = {'127.0.0.1', '::1', 'localhost'}
SOCKETPAIR_SETUP = ContextVar('report_test_socketpair_setup', default=False)


def require_host(host, *, allow_loopback, network_attempts, operation, runtime_ipc_attempts=None):
    if allow_loopback and isinstance(host, str) and host in LOCAL_HOSTS:
        return
    if operation == 'connect' and SOCKETPAIR_SETUP.get() and host in ('127.0.0.1', '::1'):
        if runtime_ipc_attempts is not None:
            runtime_ipc_attempts.append('socketpair.connect')
        return
    if network_attempts is not None:
        network_attempts.append(operation)
    raise AssertionError('Networking is forbidden by the selected report test policy')


def guarded_connect(original_connect, *, allow_loopback=True, network_attempts=None,
                    operation='connect', runtime_ipc_attempts=None):
    def connect(instance, address):
        host = address[0] if isinstance(address, tuple) and address else ''
        require_host(host, allow_loopback=allow_loopback, network_attempts=network_attempts,
                     operation=operation, runtime_ipc_attempts=runtime_ipc_attempts)
        return original_connect(instance, address)
    return connect


def guarded_getaddrinfo(original_getaddrinfo, *, allow_loopback=True, network_attempts=None):
    def getaddrinfo(host, *args, **kwargs):
        require_host(host, allow_loopback=allow_loopback, network_attempts=network_attempts, operation='getaddrinfo')
        return original_getaddrinfo(host, *args, **kwargs)
    return getaddrinfo


def guarded_create_connection(original_create, *, allow_loopback=True, network_attempts=None):
    def create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else ''
        require_host(host, allow_loopback=allow_loopback, network_attempts=network_attempts, operation='create_connection')
        return original_create(address, *args, **kwargs)
    return create_connection


def guarded_socketpair(original_socketpair):
    def socketpair(*args, **kwargs):
        token = SOCKETPAIR_SETUP.set(True)
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            SOCKETPAIR_SETUP.reset(token)
    return socketpair


def test_settings(temp):
    for key in tuple(os.environ):
        if key.startswith(('METRICS_', 'DJANGO_')) or key in {'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS'}:
            del os.environ[key]
    os.environ.update({
        'METRICS_STATE_DIR': str(temp / 'state'),
        'METRICS_SQLITE_DATABASE_PATH': str(temp / 'catalog.sqlite3'),
        'METRICS_TASK_SEARCH_CACHE_DIR': str(temp / 'task-cache'),
        'METRICS_PROJECT_ARCHIVE_ROOT': str(temp / 'archive'),
        'METRICS_JIRA_SERVER_URL': 'https://tracker.example.test',
        'METRICS_JIRA_AUTH_MODE': 'server_pat',
        'METRICS_JIRA_API_TOKEN': 'synthetic-only-token',
        'SECRET_KEY': 'synthetic-authoring-ui-tests-only',
        'DEBUG': 'true',
    })
    with patch('environs.Env.read_env', lambda *args, **kwargs: None):
        defaults = importlib.import_module('metrics.settings.defaults_metrics')
    values = {key: value for key, value in vars(defaults).items() if key.isupper()}
    values.update({
        'ALLOWED_HOSTS': ['testserver', '127.0.0.1', 'localhost'],
        'DATABASES': {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        'STATIC_ROOT': temp / 'static',
        'METRICS_PROJECT_RUN_ENABLED': False,
        'METRICS_PROJECT_LOCAL_OPERATOR_USERNAME': '',
        'PASSWORD_HASHERS': ['django.contrib.auth.hashers.MD5PasswordHasher'],
    })
    values['STATIC_ROOT'].mkdir()
    return values


def run_tests(arguments, *, allow_loopback=True, network_attempts=None, runtime_ipc_attempts=None):
    if type(allow_loopback) is not bool:
        raise ValueError('allow_loopback must be a boolean')
    temp_parent = ROOT / 'tmp_ui_validation'
    temp_parent.mkdir(exist_ok=True)
    options = {'allow_loopback': allow_loopback, 'network_attempts': network_attempts}
    with TemporaryDirectory(prefix='report-authoring-test-', dir=temp_parent) as temporary:
        with patch.object(socket.socket, 'connect', guarded_connect(
                socket.socket.connect, runtime_ipc_attempts=runtime_ipc_attempts, **options)), \
                patch.object(socket.socket, 'connect_ex', guarded_connect(socket.socket.connect_ex, operation='connect_ex', **options)), \
                patch.object(socket, 'create_connection', guarded_create_connection(socket.create_connection, **options)), \
                patch.object(socket, 'getaddrinfo', guarded_getaddrinfo(socket.getaddrinfo, **options)), \
                patch.object(socket, 'socketpair', guarded_socketpair(socket.socketpair)):
            settings.configure(**test_settings(Path(temporary)))
            django.setup()
            return int(pytest.main(arguments))


if __name__ == '__main__':
    raise SystemExit(run_tests(sys.argv[1:]))
