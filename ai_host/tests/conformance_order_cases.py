import json
import threading
from urllib.parse import urlsplit
from wsgiref.util import setup_testing_defaults

from django.test import override_settings
import pytest

from ai_host.tests import conformance_urls
from ai_host.tests.conformance_host_cases import identity_package
from ai_host.tests.conformance_runtime_probe import AssetParser
from ai_host.wiring import build_wsgi_application


HOP_BY_HOP_HEADERS = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailer', 'transfer-encoding', 'upgrade',
}


def header_map(response):
    return {key.lower(): value for key, value in response.headers}


def host_headers(server, credentials, *, authenticated, host=None):
    headers = (('Host', host or urlsplit(server.base_url).netloc),)
    if authenticated:
        return (*headers, *credentials.headers(credentials.owner))
    return headers


def runtime_asset_path(server, credentials):
    response = server.request(
        'GET', server.root_path + '/', headers=host_headers(server, credentials, authenticated=True), timeout=3,
    )
    assert response.status == 200
    parser = AssetParser(server.root_path + '/assets/')
    parser.feed(response.body.decode('utf-8'))
    assert parser.assets
    return parser.assets[0]


def order_targets(server, asset_path):
    return (
        ('django', '/django-identity/'),
        ('runtime-root', server.root_path),
        ('runtime-api', server.root_path + '/apps/probe/api/identity'),
        ('runtime-asset', asset_path),
    )


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


@pytest.mark.parametrize('authenticated', [False, True])
def test_waitress_invalid_host_matrix_precedes_authentication_and_shutdown(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials, authenticated,
):
    visits = []
    conformance_urls.VISITS.clear()
    accepting = threading.Event()
    accepting.set()
    with override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls'):
        with ai_host_factory(
            settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
            apps=(identity_package(visits),), start_timeout=15.0,
        ) as session:
            with ai_server_factory(session, accepting_requests=accepting.is_set) as server:
                asset = runtime_asset_path(server, ai_credentials)
                for running in (True, False):
                    if running:
                        accepting.set()
                    else:
                        accepting.clear()
                    for label, target in order_targets(server, asset):
                        response = server.request(
                            'GET', target,
                            headers=host_headers(
                                server, ai_credentials, authenticated=authenticated,
                                host='rebind.attacker.example',
                            ),
                            timeout=2,
                        )
                        headers = header_map(response)
                        assert response.status == 400, (label, running, response)
                        assert response.body == b'Bad Request'
                        assert 'www-authenticate' not in headers
                        assert 'retry-after' not in headers
        assert visits == conformance_urls.VISITS == []


@pytest.mark.parametrize('authenticated', [False, True])
def test_waitress_stopping_valid_host_matrix_returns_fixed_503_before_authentication(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials, authenticated,
):
    visits = []
    conformance_urls.VISITS.clear()
    accepting = threading.Event()
    accepting.set()
    with override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls'):
        with ai_host_factory(
            settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
            apps=(identity_package(visits),), start_timeout=15.0,
        ) as session:
            with ai_server_factory(session, accepting_requests=accepting.is_set) as server:
                asset = runtime_asset_path(server, ai_credentials)
                accepting.clear()
                for label, target in order_targets(server, asset):
                    response = server.request(
                        'GET', target,
                        headers=host_headers(server, ai_credentials, authenticated=authenticated),
                        timeout=2, close_connection=False,
                    )
                    headers = header_map(response)
                    assert response.status == 503, (label, response)
                    assert response.body == b'Service Unavailable'
                    assert headers['retry-after'] == '2'
                    assert headers['content-length'] == '19'
                    assert 'www-authenticate' not in headers
                    assert 'location' not in headers
                    assert HOP_BY_HOP_HEADERS.isdisjoint(headers)
        assert visits == conformance_urls.VISITS == []


def test_waitress_running_order_authenticates_before_redirect_assets_and_dispatch(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials,
):
    visits = []
    conformance_urls.VISITS.clear()
    with override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls'):
        with ai_host_factory(
            settings=ai_clock_and_limits.settings, config=ai_clock_and_limits.config,
            apps=(identity_package(visits),), start_timeout=15.0,
        ) as session:
            with ai_server_factory(session) as server:
                asset = runtime_asset_path(server, ai_credentials)
                targets = dict(order_targets(server, asset))
                for label, target in targets.items():
                    response = server.request(
                        'GET', target, headers=host_headers(server, ai_credentials, authenticated=False), timeout=2,
                    )
                    headers = header_map(response)
                    assert response.status == 401, (label, response)
                    assert headers['www-authenticate'] == ai_clock_and_limits.config.www_authenticate
                    assert 'location' not in headers

                assert visits == conformance_urls.VISITS == []

                django = server.request(
                    'GET', targets['django'],
                    headers=host_headers(server, ai_credentials, authenticated=True), timeout=2,
                )
                assert django.status == 200
                assert json.loads(django.body) == {'principal': ai_credentials.owner.id}

                root_redirect = server.request(
                    'GET', targets['runtime-root'],
                    headers=host_headers(server, ai_credentials, authenticated=True), timeout=2,
                )
                assert root_redirect.status == 308
                assert header_map(root_redirect)['location'] == server.root_path + '/'
                assert root_redirect.body == b''

                runtime = server.request(
                    'GET', targets['runtime-api'],
                    headers=host_headers(server, ai_credentials, authenticated=True), timeout=2,
                )
                assert runtime.status == 200
                assert json.loads(runtime.body) == {'principal': ai_credentials.owner.id}

                asset_response = server.request(
                    'GET', targets['runtime-asset'],
                    headers=host_headers(server, ai_credentials, authenticated=True), timeout=2,
                )
                assert asset_response.status == 200
                assert asset_response.body
                assert visits == [ai_credentials.owner.id]
                assert conformance_urls.VISITS == [ai_credentials.owner.id]
