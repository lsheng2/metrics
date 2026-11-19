from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
from urllib.parse import urlsplit

from django.test import override_settings
import pytest

from ai_base_runtime import RuntimeCallTimeout
from ai_base_runtime.spi import HttpLimits
from ai_host.tests.conformance_runtime_probe import AssetParser, Events, RuntimeProbe, until


@contextmanager
def host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits, *, config=None):
    probe = RuntimeProbe()
    selected = config or replace(
        ai_clock_and_limits.config,
        http_limits=HttpLimits(max_streams=4, max_requests=4, short_request_timeout_seconds=0.3),
    )
    with ai_host_factory(
        settings=ai_clock_and_limits.settings, config=selected,
        apps=(probe.package(),), start_timeout=15,
    ) as session:
        probe.handle = session.handle
        with ai_server_factory(session) as server:
            try:
                yield probe, session, server
            finally:
                probe.release()


def auth_headers(server, credentials, host=None):
    return (('Host', host or urlsplit(server.base_url).netloc), *credentials.headers(credentials.owner))


def path(server, name):
    return server.root_path + '/apps/qualification/api/qualification/' + name


def asset_path(server, credentials):
    response = server.request('GET', server.root_path + '/', headers=auth_headers(server, credentials), timeout=3)
    assert response.status == 200
    parser = AssetParser(server.root_path + '/assets/')
    parser.feed(response.body.decode())
    assert parser.assets
    return parser.assets[0]


@pytest.mark.parametrize('host', ['127.0.0.1:8793', 'localhost:8793', '[::1]:8793', 'configured.example:8793'])
def test_valid_host_forms_share_auth_and_assets(ai_host_mode, ai_host_factory, ai_server_factory,
                                              ai_clock_and_limits, ai_credentials, host):
    config = replace(ai_clock_and_limits.config, allowed_hosts=('127.0.0.1', 'localhost', '[::1]', 'configured.example'))
    with override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls'):
        with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits, config=config) as (_, _, server):
            asset = asset_path(server, ai_credentials)
            for target in ('/django-identity/', path(server, 'echo'), asset):
                response = server.request('GET', target, headers=auth_headers(server, ai_credentials, host), timeout=3)
                assert response.status == 200, (target, response)
                unauth = server.request('GET', target, headers=(('Host', host),), timeout=3)
                assert unauth.status == 401
                assert {key.lower(): value for key, value in unauth.headers}['www-authenticate'] == config.www_authenticate


def test_auth_saturation_cannot_consume_an_authenticated_slot(ai_host_mode, ai_host_factory, ai_server_factory,
                                                            ai_clock_and_limits, ai_credentials):
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (probe, session, server):
        def unauthorized(_):
            return server.request('GET', path(server, 'slow'), headers=(('Host', urlsplit(server.base_url).netloc),), timeout=2)

        with ThreadPoolExecutor(max_workers=12) as pool:
            assert all(response.status == 401 for response in pool.map(unauthorized, range(24)))
        assert probe.count('short') == 0
        assert server.request('GET', path(server, 'echo'), headers=auth_headers(server, ai_credentials), timeout=2).status == 200
        snapshot = session.handle.blocking.diagnostics.snapshot(ai_credentials.owner, timeout=1)
        assert snapshot.short_in_flight_count == 0


def test_four_stream_slots_do_not_starve_short_calls_or_assets(ai_host_mode, ai_host_factory, ai_server_factory,
                                                             ai_clock_and_limits, ai_credentials):
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (probe, session, server):
        asset = asset_path(server, ai_credentials)
        streams = []
        try:
            for _ in range(4):
                stream = server.open_stream(path(server, 'active'), headers=auth_headers(server, ai_credentials), timeout=3)
                streams.append(stream)
                assert Events(stream).next()['type'] == 'chunk'
            rejected = server.request('GET', path(server, 'active'), headers=auth_headers(server, ai_credentials), timeout=2)
            assert rejected.status == 503 and dict(rejected.headers)['Retry-After'] == '2'
            for target in (path(server, 'echo'), asset):
                assert server.request('GET', target, headers=auth_headers(server, ai_credentials), timeout=2).status == 200
        finally:
            for stream in streams:
                stream.close()
        until(lambda: probe.count('streams') == 0)
        assert session.handle.blocking.diagnostics.snapshot(ai_credentials.owner, timeout=1).stream_in_flight_count == 0


def test_blocked_loop_leaves_assets_available_and_cancels_timed_out_facade(ai_host_mode, ai_host_factory,
                                                                      ai_server_factory, ai_clock_and_limits,
                                                                      ai_credentials):
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (probe, session, server):
        asset = asset_path(server, ai_credentials)
        chat = session.handle.blocking.chat
        assert chat.list_sessions(ai_credentials.owner, app_id='qualification', limit=100, timeout=1) == ()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(
                server.request, 'GET', path(server, 'lag'), headers=auth_headers(server, ai_credentials), timeout=3,
            )
            try:
                assert probe.loop_entered.wait(1)
                assert server.request('GET', asset, headers=auth_headers(server, ai_credentials), timeout=1).status == 200
                with pytest.raises(RuntimeCallTimeout):
                    chat.open_session(ai_credentials.owner, app_id='qualification', agent='agent',
                                      session_key='must-not-be-created', timeout=0.05)
                timed_out = pending.result(timeout=2)
                assert timed_out.status in {503, 504}
            finally:
                probe.loop_release.set()
        until(lambda: session.handle.blocking.diagnostics.snapshot(ai_credentials.owner, timeout=1).loop_stall_count > 0)
        assert chat.list_sessions(ai_credentials.owner, app_id='qualification', limit=100, timeout=1) == ()
        assert session.handle.blocking.diagnostics.snapshot(ai_credentials.owner, timeout=1).loop_lag_max_seconds > 0


def test_loop_thread_facade_misuse_fails_without_deadlock(ai_host_mode, ai_host_factory, ai_server_factory,
                                                        ai_clock_and_limits, ai_credentials):
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (_, _, server):
        response = server.request('GET', path(server, 'misuse'), headers=auth_headers(server, ai_credentials), timeout=2)
        assert response.status == 200
        assert json.loads(response.body) == {'code': 'runtime_usage_invalid'}
