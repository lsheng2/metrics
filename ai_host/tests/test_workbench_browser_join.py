from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

from ai_base_runtime.testkit import scripted_model_endpoint


@contextmanager
def running_workbench(tmp_path, endpoint):
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    stop = tmp_path / 'stop.flag'
    log_path = tmp_path / 'workbench.log'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with log_path.open('wb') as log:
        process = subprocess.Popen([
            sys.executable, '-I', str(root / 'ai_host/tests/workbench_serve_entry.py'),
            str(tmp_path), str(port), str(stop), endpoint.model.base_url,
        ], cwd=root, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        forced = False
        try:
            deadline = time.monotonic() + 45
            while True:
                assert process.poll() is None, log_path.read_text(encoding='utf-8', errors='replace')
                try:
                    with opener.open(base + '/', timeout=2) as response:
                        assert response.status == 200
                        break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline, log_path.read_text(encoding='utf-8', errors='replace')
                    time.sleep(0.1)
            events = [json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines()
                      if line.startswith('{"event": "browser_scopes"')]
            assert len(events) == 1
            yield base, events[0]
        finally:
            stop.write_text('stop\n', encoding='utf-8')
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                forced = True
                process.kill()
                process.wait(timeout=5)
            (tmp_path / 'stop-result.json').write_text(json.dumps({
                'returncode': process.returncode, 'forced': forced, 'pid': process.pid,
            }), encoding='utf-8')
        assert process.returncode == 0 and not forced, log_path.read_text(encoding='utf-8', errors='replace')
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(('127.0.0.1', port)) != 0


@pytest.mark.browser
def test_real_workbench_preserves_session_frame_and_uses_installed_embed_protocol(tmp_path):
    completion = {
        'id': 'workbench-reply', 'object': 'chat.completion', 'created': 1794780000,
        'model': 'scripted', 'choices': [{
            'index': 0, 'message': {'role': 'assistant', 'content': 'Synthetic workbench reply.'},
            'finish_reason': 'stop',
        }],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
    }
    with scripted_model_endpoint([completion]) as endpoint, running_workbench(tmp_path, endpoint) as (base, scopes):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.set_default_timeout(10000)
            errors = []
            requests = []
            asset_responses, asset_failures, cold_assets, cold_asset_requests = [], [], [], []
            asset_prefix = base + '/ai/assets/'
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append((request.method, request.url)))
            page.on('response', lambda response: asset_responses.append({
                'url': response.url, 'status': response.status,
            }) if response.url.startswith(asset_prefix) else None)
            page.on('requestfailed', lambda request: asset_failures.append(request.url)
                    if request.url.startswith(asset_prefix) else None)
            url = f'{base}/workbench/?scope_id={scopes["scope"]}&begin=2026-08-03&end=2026-08-09'
            try:
                assert page.goto(url).status == 200
                initial_title = page.title()
                iframe = page.locator('.workbench-ai-chat-frame')
                iframe.wait_for()
                frame = iframe.element_handle().content_frame()
                frame.wait_for_load_state('domcontentloaded')
                frame.evaluate("window.frameIdentity = 'preserved'")
                initial_src = iframe.get_attribute('src')
                page.wait_for_function("document.querySelector('.workbench-ai-chat-frame').dataset.embedHostReady === 'true'")
                page.locator('[data-workbench-ticket-checkbox]').check()
                page.locator('[data-workbench-ticket-row] [data-workbench-field="summary"]').click()
                page.locator('[data-workbench-ticket-ask-ai]').click()
                page.wait_for_function("""() =>
                    JSON.parse(document.getElementById('workbench-ai-context').textContent)
                        .runtime.context_ref.values.ticket_ids[0] === 'SAMPLE-1'""")
                assert page.title() == initial_title
                frame.get_by_role('textbox', name='Message composer').fill('Summarize this synthetic scope.')
                frame.get_by_role('button', name='Send message').click()
                page.wait_for_function("""() =>
                    document.querySelector('.workbench-ai-chat-frame').contentDocument.body.innerText
                        .includes('Synthetic workbench reply.')""")
                assert len(endpoint.requests) == 1
                frame.wait_for_load_state('load')
                frame.evaluate('() => document.fonts.ready.then(() => true)')
                cold_assets = list(asset_responses)
                cold_asset_requests = sorted({target for _, target in requests if target.startswith(asset_prefix)})
                assert cold_asset_requests and not asset_failures
                assert {item['url'] for item in cold_assets} == set(cold_asset_requests)
                assert all(item['status'] == 200 for item in cold_assets), cold_assets
                frame.evaluate("""() => {
                    window.contextNotices = [];
                    addEventListener('message', event => {
                        if (event.data?.type === 'context-changed') window.contextNotices.push(event.data);
                    });
                }""")
                page.locator('#workbench-end').fill('2026-08-16')
                page.locator('.workbench-apply-button').click()
                page.wait_for_function("""() =>
                    JSON.parse(document.getElementById('workbench-ai-context').textContent)
                        .runtime.context_ref.values.end === '2026-08-16'""")
                assert page.title() == initial_title
                assert iframe.get_attribute('src') == initial_src
                assert frame.evaluate('window.frameIdentity') == 'preserved'
                page.wait_for_function("""() =>
                    document.querySelector('.workbench-ai-chat-frame').contentWindow.contextNotices.length > 0""")
                assert frame.evaluate('window.contextNotices.at(-1).protocol') == 'ai-base.embed/1'
                page.locator('[data-workbench-collapse="ai-assistant"]').click()
                page.locator('[data-workbench-collapse="ai-assistant"]').click()
                assert frame.evaluate('window.frameIdentity') == 'preserved'
                page.evaluate("window.DashboardShell.applyTheme('dark')")
                page.wait_for_function("""() =>
                    document.querySelector('.workbench-ai-chat-frame').contentDocument.documentElement.dataset.theme === 'dark'""")
                page.screenshot(path=str(tmp_path / 'workbench-dark.png'))
                page.evaluate("""() => {
                    window.workbenchSwaps = 0;
                    document.body.addEventListener('htmx:afterSwap', () => window.workbenchSwaps++);
                }""")
                for action in ('metrics.openChart', 'metrics.openEvidence'):
                    before = len(requests)
                    swap_count = page.evaluate('window.workbenchSwaps')
                    frame.evaluate("""actionId => parent.postMessage({
                        protocol: 'ai-base.embed/1', type: 'host-action',
                        sessionId: location.pathname.split('/').at(-1),
                        actionId, payload: {chart_id: 'default_bug_trend'}
                    }, location.origin)""", action)
                    page.wait_for_function('count => window.workbenchSwaps > count', arg=swap_count)
                    assert 'chart_id=default_bug_trend' in page.url
                    assert any(method == 'GET' and '/workbench/' in target for method, target in requests[before:])
                    assert not any(method not in {'GET', 'HEAD'} for method, _ in requests[before:])
                    assert frame.evaluate('window.frameIdentity') == 'preserved'
                before = len(requests)
                frame.evaluate("""() => parent.postMessage({
                    type: 'ai-base.host-action.request',
                    request: {actionKind: 'metrics.openGrafanaChart'}
                }, location.origin)""")
                page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
                assert not any('/workbench/' in target for _, target in requests[before:])
                page.goto(url)
                assert page.locator('.workbench-ai-chat-frame').get_attribute('src') == initial_src
                page.goto(f'{base}/workbench/?scope_id={scopes["unresolved"]}')
                assert page.locator('.workbench-ai-chat-frame').count() == 0
                assert not errors, errors
            except BaseException:
                page.screenshot(path=str(tmp_path / 'failure.png'), full_page=True)
                (tmp_path / 'failure.html').write_text(page.content(), encoding='utf-8')
                raise
            finally:
                (tmp_path / 'browser-observations.json').write_text(json.dumps({
                    'page_errors': errors, 'requests': requests,
                    'cold_assets': cold_assets, 'cold_asset_requests': cold_asset_requests,
                }, indent=2), encoding='utf-8')
                browser.close()
