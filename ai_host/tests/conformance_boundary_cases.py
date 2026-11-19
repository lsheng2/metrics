from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from urllib.parse import urlsplit

from django.test import override_settings
from playwright.sync_api import sync_playwright

from ai_base_runtime.spi import HttpLimits
from ai_host.tests.conformance_runtime_cases import asset_path, auth_headers, host_probe, path
from ai_host.tests.conformance_runtime_probe import until
from ai_host.tests.native_stream_support import EventReader


@override_settings(ROOT_URLCONF='ai_host.tests.conformance_urls')
def test_full_short_capacity_preserves_auth_and_navigation_retry(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials,
):
    config = replace(
        ai_clock_and_limits.config,
        http_limits=HttpLimits(max_streams=4, max_requests=4, short_request_timeout_seconds=5),
    )
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits, config=config) as (probe, session, server):
        asset = asset_path(server, ai_credentials)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(extra_http_headers=dict(ai_credentials.headers(ai_credentials.owner)))
            page = context.new_page()
            try:
                assert page.goto(server.base_url + '/django-identity/').status == 200
                url = server.base_url + server.root_path + '/'
                page.evaluate("""url => {
                    const link = document.createElement('a');
                    link.id = 'runtime-retry-target';
                    link.href = url;
                    link.textContent = 'Runtime';
                    document.body.append(link);
                }""", url)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    pending = [
                        pool.submit(
                            server.request, 'GET', path(server, 'slow'),
                            headers=auth_headers(server, ai_credentials), timeout=8,
                        )
                        for _ in range(4)
                    ]
                    try:
                        until(lambda: probe.count('short') == 4)
                        assert session.handle.blocking.diagnostics.snapshot(
                            ai_credentials.owner, timeout=1,
                        ).short_in_flight_count == 4
                        unauthenticated = server.request(
                            'GET', path(server, 'echo'),
                            headers=(('Host', urlsplit(server.base_url).netloc),), timeout=2,
                        )
                        assert unauthenticated.status == 401
                        assert server.request(
                            'GET', asset, headers=auth_headers(server, ai_credentials), timeout=2,
                        ).status == 200
                        iframe_retry = server.request(
                            'GET', server.root_path + '/',
                            headers=(*auth_headers(server, ai_credentials), ('Sec-Fetch-Dest', 'iframe')),
                            timeout=2,
                        )
                        assert iframe_retry.status == 503
                        assert dict((key.lower(), value) for key, value in iframe_retry.headers)['retry-after'] == '2'
                        with page.expect_response(lambda response: response.url == url) as navigation:
                            page.locator('#runtime-retry-target').click()
                        initial = navigation.value
                        assert initial.status == 503
                        assert page.locator('meta[http-equiv="refresh"]').get_attribute('content') == '2'
                        with page.expect_response(
                            lambda response: response.url == url and response.status == 200, timeout=10000,
                        ):
                            probe.short_release.set()
                            assert all(future.result(timeout=3).status == 200 for future in pending)
                        until(lambda: session.handle.blocking.diagnostics.snapshot(
                            ai_credentials.owner, timeout=1,
                        ).short_in_flight_count == 0)
                    finally:
                        probe.release()
            finally:
                browser.close()


def test_embedded_document_restricts_frame_ancestors_to_same_origin(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials,
):
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (_, session, server):
        chat = session.handle.blocking.chat.open_session(
            ai_credentials.owner, app_id='qualification', agent='agent',
            session_key='qualification.frame-policy', timeout=2,
        )
        response = server.request(
            'GET', server.root_path + '/embed/' + chat.session_id,
            headers=auth_headers(server, ai_credentials), timeout=3,
        )
        assert response.status == 200
        headers = {key.lower(): value for key, value in response.headers}
        ancestors = [
            directive.split()
            for directive in headers['content-security-policy'].split(';')
            if directive.strip().split()[:1] == ['frame-ancestors']
        ]
        assert ancestors == [['frame-ancestors', "'self'"]]


def test_runtime_http_refuses_requests_after_close_http_and_final_stop(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials,
):
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (probe, session, server):
        target = server.root_path + '/api/apps'
        headers = auth_headers(server, ai_credentials)
        assert server.request('GET', target, headers=headers, timeout=2).status == 200
        stream = server.open_stream(path(server, 'active'), headers=headers, timeout=3)
        reader = EventReader(stream).start()
        try:
            until(lambda: bool(reader.events))
            assert reader.events[0]['payload']['type'] == 'chunk'
            assert session.handle.blocking.diagnostics.snapshot(
                ai_credentials.owner, timeout=1,
            ).stream_in_flight_count == 1
            assert session.handle.close_http().completed
            assert session.handle.blocking.diagnostics.snapshot(
                ai_credentials.owner, timeout=1,
            ).stream_in_flight_count == 0
            reader.finish()
        finally:
            probe.release()
            stream.close()
            reader.thread.join(timeout=3)
            assert not reader.thread.is_alive()
        assert server.request('GET', target, headers=headers, timeout=2).status == 503
        assert session.handle.stop().completed
        assert server.request('GET', target, headers=headers, timeout=2).status == 503
