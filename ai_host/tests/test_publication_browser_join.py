import json
from contextlib import closing
from pathlib import Path
import sqlite3
import time

import pytest
from playwright.sync_api import expect, sync_playwright

from ai_base_runtime.testkit import scripted_model_endpoint
from ai_base_runtime.contracts import canonical_json
from ai_host.tests.publication_model_fixture import publication_responses
from ai_host.tests.publication_process_fixture import request_json, running_publication_stack


def wait_json(url, credentials, predicate, *, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        result = request_json(url, credentials=credentials)
        if predicate(result):
            return result
        assert time.monotonic() < deadline, result
        time.sleep(0.1)


def audit_events(database, approval_id):
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(
            'SELECT category, sequence, approval_id, tool_call_id, principal_id, result_status '
            'FROM ai_host_runtimeauditevent WHERE approval_id = ? ORDER BY sequence',
            (approval_id,),
        )]


@pytest.mark.browser
def test_real_workbench_approval_imports_chart_and_correlates_history(tmp_path):
    with scripted_model_endpoint(publication_responses()) as endpoint:
        with running_publication_stack(tmp_path / 'joined', endpoint) as stack:
            base, credentials = stack['base'], stack['credentials']
            assert stack['settings'] == 'metrics.settings.production'
            assert stack['basic_from_environment']
            assert not stack['debug'] and not stack['anonymous_approval']
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    http_credentials=credentials, viewport={'width': 1440, 'height': 1000},
                )
                page = context.new_page()
                page.set_default_timeout(15000)
                errors, messages = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda request: messages.append(request.post_data_json)
                        if request.method == 'POST' and request.url.endswith('/ai/api/chat/messages') else None)
                try:
                    response = page.goto(
                        f'{base}/workbench/?scope_id={stack["scope"]}&begin=2026-08-03&end=2026-08-30',
                    )
                    assert response.status == 200
                    initial_title = page.title()
                    iframe = page.locator('.workbench-ai-chat-frame')
                    iframe.wait_for()
                    frame = iframe.element_handle().content_frame()
                    frame.wait_for_load_state('domcontentloaded')
                    initial_src = iframe.get_attribute('src')
                    frame.evaluate("window.publicationFrameIdentity = 'preserved'")
                    composer = frame.get_by_role('textbox', name='Message composer')
                    expect(composer).to_be_enabled(timeout=20000)
                    composer.fill('Validate and publish the synthetic new critical/high chart for WW32 to WW35.')
                    frame.get_by_role('button', name='Send message').click()
                    approvals_url = base + '/ai/api/approvals?appId=metrics&limit=20'
                    approvals = wait_json(
                        approvals_url, credentials,
                        lambda value: any(row['state'] == 'pending' for row in value),
                    )
                    approval = next(row for row in approvals if row['state'] == 'pending')
                    assert request_json(base + '/api/ai-publish-history/', credentials=credentials)['items'] == []
                    assert b'draft_validated' in canonical_json(endpoint.requests[2])
                    page.locator('#workbench-end').fill('2026-08-31')
                    page.locator('.workbench-apply-button').click()
                    page.wait_for_function("""() =>
                        JSON.parse(document.getElementById('workbench-ai-context').textContent)
                            .runtime.context_ref.values.end === '2026-08-31'""")
                    assert iframe.get_attribute('src') == initial_src
                    current_approval = request_json(
                        base + '/ai/api/approvals/' + approval['approvalId'], credentials=credentials,
                    )
                    assert current_approval['state'] == 'pending'
                    page.locator('[data-workbench-collapse="ai-assistant"]').click()
                    page.locator('[data-workbench-collapse="ai-assistant"]').click()
                    assert frame.evaluate('window.publicationFrameIdentity') == 'preserved'
                    details = frame.get_by_role('tab', name='Details', exact=True)
                    if details.is_visible():
                        details.click()
                    approve = frame.get_by_role('button', name='Approve approval')
                    expect(approve).to_be_enabled(timeout=15000)
                    page.screenshot(path=str(tmp_path / 'approval-pending.png'), full_page=True)
                    approve.click()
                    history = wait_json(
                        base + '/api/ai-publish-history/', credentials,
                        lambda value: bool(value['items']),
                    )
                    published = history['items'][0]
                    assert published['status'] == 'published', published
                    assert published['approval_id'] == approval['approvalId']
                    assert published['actor'] == credentials['username']
                    assert published['requested_series'] == ['new_critical_high']
                    assert (published['range_start'], published['range_end']) == ('26WW32', '26WW35')
                    assert published['latest']
                    stored = request_json(
                        stack['grafana'] + '/api/dashboards/uid/' + published['dashboard_uid'],
                        credentials=credentials,
                    )
                    dashboard = stored['dashboard']
                    assert dashboard['time'] == {'from': '2026-08-03T00:00:00', 'to': '2026-08-30T23:59:59'}
                    assert dashboard['uid'] == published['dashboard_uid']
                    variables = {item['name']: item['current']['value'] for item in dashboard['templating']['list']}
                    assert variables['profile_id'] == 'chiplet-2a-jira'
                    assert variables['begin_ww'] == '26WW32' and variables['end_ww'] == '26WW35'
                    assert iframe.get_attribute('src') == initial_src
                    wait_json(
                        base + '/ai/api/chat/runs/' + published['run_id'], credentials,
                        lambda value: value['status'] == 'succeeded',
                    )
                    assert len(messages) == 1
                    repeated = request_json(
                        base + '/ai/api/chat/messages', credentials=credentials, payload=messages[0],
                    )
                    assert repeated['runId'] == published['run_id']
                    assert len(request_json(base + '/api/ai-publish-history/', credentials=credentials)['items']) == 1
                    assert len(endpoint.requests) == 4
                    events = audit_events(stack['database'], published['approval_id'])
                    assert [row['category'] for row in events] == [
                        'approval_requested', 'approval_decided', 'approval_consumed', 'tool_result',
                    ], events
                    assert all(row['tool_call_id'] == published['tool_call_id'] for row in events)
                    (tmp_path / 'publication-receipt.json').write_text(json.dumps({
                        'runtime_candidate': json.loads(Path('ai_host/runtime_artifact.json').read_text()),
                        'grafana': stack['grafana_health'], 'publication': published,
                        'audit': events, 'model_requests': len(endpoint.requests),
                        'page_errors': errors,
                    }, indent=2), encoding='utf-8')
                    history_pane = page.locator('[data-workbench-publication-history]')
                    history_pane.locator('summary span').click()
                    history_pane.get_by_role('link', name='Refresh', exact=True).click()
                    expect(history_pane.locator(
                        f'[data-approval-id="{published["approval_id"]}"] code[title="{published["approval_id"]}"]',
                    )).to_be_visible()
                    assert page.title() == initial_title
                    assert iframe.get_attribute('src') == initial_src
                    assert frame.evaluate('window.publicationFrameIdentity') == 'preserved'
                    page.screenshot(path=str(tmp_path / 'published-history.png'), full_page=True)
                    with page.expect_response(lambda result: '/api/ds/query' in result.url, timeout=60000) as query:
                        page.goto(published['grafana_url'])
                    query_result = query.value.json()
                    (tmp_path / 'grafana-query.json').write_text(json.dumps(query_result, indent=2), encoding='utf-8')
                    page.screenshot(path=str(tmp_path / 'grafana-chart.png'), full_page=True)
                    result = query_result['results']['A']
                    assert not result.get('error'), result
                    assert result['frames'], result
                    fields = result['frames'][0]['schema']['fields']
                    assert any(field['type'] == 'time' for field in fields), fields
                    assert any(field['name'] == 'new_critical_high' for field in fields), fields
                    values = dict(zip(
                        (field['name'] for field in fields), result['frames'][0]['data']['values'], strict=True,
                    ))
                    assert values['new_critical_high'] == [1, 0, 0, 0]
                    assert values['bucket_start'] == [
                        1785715200000, 1786320000000, 1786924800000, 1787529600000,
                    ]
                    assert not errors, errors
                except BaseException:
                    page.screenshot(path=str(tmp_path / 'failure.png'), full_page=True)
                    (tmp_path / 'failure.html').write_text(page.content(), encoding='utf-8')
                    (tmp_path / 'model-requests.json').write_bytes(canonical_json(endpoint.requests))
                    raise
                finally:
                    browser.close()
