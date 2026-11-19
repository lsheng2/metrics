import io
import json
import socket

from django.core.management.base import CommandError
from django.test import override_settings
import pytest

from ai_host.management.commands.serve import Command


@pytest.mark.parametrize('host', ['0.0.0.0', '192.0.2.7', 'dashboard.example', '::'])
@override_settings(AI_HOST_ALLOW_ANONYMOUS_APPROVAL=True)
def test_anonymous_approval_cannot_be_exposed_by_a_network_bind(monkeypatch, host):
    def unexpected_socket(*args, **kwargs):
        pytest.fail('binding policy must run before acquiring a socket')

    monkeypatch.setattr(socket, 'socket', unexpected_socket)
    with pytest.raises(CommandError, match='anonymous'):
        Command()._bind_listener(host, 0)


@pytest.mark.parametrize('host', ['127.0.0.1', '127.0.0.2', 'localhost', '::1'])
@override_settings(AI_HOST_ALLOW_ANONYMOUS_APPROVAL=True, METRICS_BASIC_AUTH_USERS=None)
def test_loopback_binding_retains_local_anonymous_operation(host):
    listener = Command()._bind_listener(host, 0)
    listener.close()


@override_settings(AI_HOST_ALLOW_ANONYMOUS_APPROVAL=False, METRICS_BASIC_AUTH_USERS=None)
def test_production_anonymous_network_bind_warns_with_only_its_address():
    output = io.StringIO()
    listener = Command(stdout=output)._bind_listener('0.0.0.0', 0)
    listener.close()
    assert json.loads(output.getvalue()) == {
        'event': 'serve_anonymous_network_bind', 'host': '0.0.0.0',
    }


@override_settings(
    AI_HOST_ALLOW_ANONYMOUS_APPROVAL=False,
    METRICS_BASIC_AUTH_USERS={'synthetic-owner': 'synthetic-password'},
)
def test_authenticated_network_bind_has_no_anonymous_warning():
    output = io.StringIO()
    listener = Command(stdout=output)._bind_listener('0.0.0.0', 0)
    listener.close()
    assert output.getvalue() == ''


def test_static_file_changes_require_restart(settings):
    assert settings.WHITENOISE_AUTOREFRESH is False
