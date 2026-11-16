import socket

import pytest

from ai_host.management.commands.serve import Command


def test_isolated_django_system_checks_accept_embedded_host_registration():
    from django.core.checks import run_checks
    assert not [issue for issue in run_checks() if issue.is_serious()]


def test_shouldBindOwnedPortZeroForTests():
    command = Command()
    listener = command._bind_listener('127.0.0.1', 0)
    try:
        host, port = listener.getsockname()
        assert host == '127.0.0.1'
        assert port > 0
    finally:
        listener.close()


def test_shouldReportBindFailureBeforeRuntimeStartup(monkeypatch):
    command = Command()
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(('127.0.0.1', 0))
    occupied.listen()
    port = occupied.getsockname()[1]
    called = {'runtime': False}
    monkeypatch.setattr(command, '_run_bound_server', lambda listener, options: called.update(runtime=True))

    try:
        with pytest.raises(SystemExit) as raised:
            command.handle(host='127.0.0.1', port=port, stop_file=None, lifetime_seconds=1)
    finally:
        occupied.close()

    assert raised.value.code == 1
    assert called['runtime'] is False
