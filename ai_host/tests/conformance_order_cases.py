from wsgiref.util import setup_testing_defaults

from django.test import override_settings
import pytest

from ai_host.wiring import build_wsgi_application


def observe_rejection(path, *, host, accepting, authenticated):
    def no_dispatch(environ, start_response):
        raise AssertionError('A rejected request reached a child application.')

    environ = {}
    setup_testing_defaults(environ)
    environ.update(PATH_INFO=path, HTTP_HOST=host)
    if authenticated:
        environ['HTTP_AUTHORIZATION'] = 'Basic synthetic-not-forwarded'
    response = {}

    def start_response(status, headers, exc_info=None):
        response.update(status=status, headers=dict(headers))

    app = build_wsgi_application(no_dispatch, no_dispatch, is_accepting_requests=lambda: accepting)
    response['body'] = b''.join(app(environ, start_response))
    return response


@pytest.mark.parametrize('path', ['/', '/metrics/ai', '/metrics/ai/assets/manifest.json'])
@pytest.mark.parametrize('authenticated', [False, True])
@pytest.mark.parametrize('accepting', [False, True])
@override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='/metrics')
def test_invalid_host_precedes_shutdown_and_authentication(path, authenticated, accepting):
    result = observe_rejection(
        path, host='rebind.attacker.example', accepting=accepting, authenticated=authenticated,
    )
    assert result == {
        'status': '400 Bad Request',
        'headers': {'Content-Type': 'text/plain', 'Content-Length': '11'},
        'body': b'Bad Request',
    }


@pytest.mark.parametrize('path', ['/', '/metrics/ai', '/metrics/ai/assets/manifest.json'])
@pytest.mark.parametrize('authenticated', [False, True])
@override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='/metrics')
def test_stopping_host_rejects_all_valid_host_paths_without_hop_headers(path, authenticated):
    result = observe_rejection(
        path, host='127.0.0.1', accepting=False, authenticated=authenticated,
    )
    assert result == {
        'status': '503 Service Unavailable',
        'headers': {'Content-Type': 'text/plain', 'Content-Length': '19', 'Retry-After': '2'},
        'body': b'Service Unavailable',
    }
