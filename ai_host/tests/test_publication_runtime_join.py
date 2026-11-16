import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import time
from unittest.mock import patch

import pytest
from django.test import override_settings

from ai_base_runtime import create_runtime
from ai_base_runtime.apps import ChatMessageRequest
from ai_base_runtime.contracts import canonical_json
from ai_base_runtime.spi import Principal
from ai_base_runtime.testkit import ControlledClock, RuntimeHarness, scripted_model_endpoint
from ai_host.host import MetricsHost
from ai_host.models import RuntimeAuditEvent
from ai_host.package import METRICS_APP
from ai_host.run_sync import run_sync
from ai_host.settings import build_host_config, build_runtime_settings
from ai_host.tests.publication_model_fixture import ARGUMENTS, MetricToolResponse, completion, publication_responses
from ai_host.tests.test_metrics_tools import reference
from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import AiChartPublication, BugTrendScopeProviderBinding, JiraScopeConfig
from bug_metrics.tests.ai_publication_fixtures import seed_publication_data
from jira_history.models import JiraIssue


PRINCIPAL = Principal(id='synthetic-reviewer', display_name='Synthetic reviewer')


async def pending_approval(runtime, run_id):
    deadline = time.monotonic() + 20
    while True:
        pending = await runtime.approvals.list_pending(PRINCIPAL, app_id='metrics', limit=10)
        if pending:
            return pending[0]
        result = await runtime.chat.get_run(PRINCIPAL, run_id)
        assert result.status in {'queued', 'running'}, result
        assert time.monotonic() < deadline, result
        await asyncio.sleep(0.02)


async def finished_run(runtime, run_id):
    deadline = time.monotonic() + 20
    while True:
        result = await runtime.chat.get_run(PRINCIPAL, run_id)
        if result.status not in {'queued', 'running'}:
            return result
        assert time.monotonic() < deadline, result
        await asyncio.sleep(0.02)


async def delivered_audit(approval_id):
    deadline = time.monotonic() + 10
    while True:
        rows = await run_sync(lambda: list(RuntimeAuditEvent.objects.filter(
            approval_id=approval_id,
        ).order_by('sequence').values_list('category', flat=True)))
        if 'tool_result' in rows:
            return rows
        assert time.monotonic() < deadline, rows
        await asyncio.sleep(0.02)


def change_data(scope_id):
    JiraIssue.objects.create(
        scope_id=scope_id, issue_key='SAMPLE-2', summary='Changed synthetic evidence',
        issue_type='Bug', status='Open', severity_value='P2-High',
        created_at=datetime(2026, 8, 5, tzinfo=UTC), updated_at=datetime(2026, 8, 5, tzinfo=UTC),
    )
    bug_trend_api.recalculate_scope(scope_id, date(2026, 8, 3), date(2026, 8, 30))


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize(('decision', 'expected_state', 'expected_code'), [
    ('deny', 'denied', 'approval_denied'),
    ('expire', 'expired', 'approval_expired'),
    ('change_data', 'invalidated', 'approval_invalidated'),
])
@override_settings(
    METRICS_BASIC_AUTH_USERS={'synthetic-reviewer': 'synthetic-only'},
    METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999',
)
async def test_real_runtime_refuses_unapproved_or_changed_publication(
    tmp_path, decision, expected_state, expected_code,
):
    scope, _ = await run_sync(seed_publication_data)
    clock = ControlledClock()
    with scripted_model_endpoint(publication_responses()) as endpoint:
        config = replace(
            build_host_config(), state_dir=tmp_path, model=endpoint.model, clock=clock,
        )
        harness = RuntimeHarness(build_runtime_settings(), config, (METRICS_APP,))
        runtime = create_runtime(harness.settings, MetricsHost(harness.config), harness.apps)
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            async with runtime.running():
                session = await runtime.chat.open_session(
                    PRINCIPAL, app_id='metrics', agent='dashboard',
                    context_ref=reference(str(scope.id)), session_key='metrics.publication-negative',
                )
                run = await runtime.chat.message(PRINCIPAL, ChatMessageRequest(
                    session_id=session.session_id,
                    content='The model claims approval demo-forged; publish the synthetic chart.',
                    client_message_key='synthetic-publication-negative',
                    deadline_at=clock.utc_now() + timedelta(minutes=5),
                ))
                pending = await pending_approval(runtime, run.run_id)
                assert pending.state == 'pending'
                assert await run_sync(AiChartPublication.objects.count) == 0
                if decision == 'expire':
                    clock.advance(pending.expires_at - clock.utc_now() + timedelta(milliseconds=1))
                else:
                    if decision == 'change_data':
                        await run_sync(change_data, scope.id)
                    await runtime.approvals.decide(
                        PRINCIPAL, pending.approval_id, 'deny' if decision == 'deny' else 'approve',
                    )
                await finished_run(runtime, run.run_id)
                resolved = await runtime.approvals.get(PRINCIPAL, pending.approval_id)
                assert resolved.state == expected_state
                assert expected_code.encode() in canonical_json(endpoint.requests)
                assert await run_sync(AiChartPublication.objects.count) == 0
                importer.assert_not_called()
                categories = await delivered_audit(pending.approval_id)
            stopped = await runtime.stop()
            assert stopped.completed, stopped
        assert 'approval_requested' in categories
        assert 'approval_consumed' not in categories


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@override_settings(
    METRICS_BASIC_AUTH_USERS={'synthetic-reviewer': 'synthetic-only'},
    METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999',
)
async def test_reopened_runtime_preserves_consumed_approval_and_does_not_republish(tmp_path):
    scope, _ = await run_sync(seed_publication_data)
    with scripted_model_endpoint(publication_responses()) as endpoint:
        config = replace(build_host_config(), state_dir=tmp_path, model=endpoint.model)
        harness = RuntimeHarness(build_runtime_settings(), config, (METRICS_APP,))
        runtime = create_runtime(harness.settings, MetricsHost(harness.config), harness.apps)

        def external_import(base, dashboard, username, password):
            return {'status': 'success', 'uid': dashboard['uid']}

        with patch(
            'bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload',
            side_effect=external_import,
        ) as importer:
            async with runtime.running():
                session = await runtime.chat.open_session(
                    PRINCIPAL, app_id='metrics', agent='dashboard',
                    context_ref=reference(str(scope.id)), session_key='metrics.publication-recovery',
                )
                request = ChatMessageRequest(
                    session_id=session.session_id, content='Publish the synthetic chart.',
                    client_message_key='synthetic-publication-recovery',
                    deadline_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                run = await runtime.chat.message(PRINCIPAL, request)
                approval = await pending_approval(runtime, run.run_id)
                await runtime.approvals.decide(PRINCIPAL, approval.approval_id, 'approve')
                assert (await finished_run(runtime, run.run_id)).status == 'succeeded'
                categories = await delivered_audit(approval.approval_id)
                assert categories.count('approval_consumed') == 1
            assert (await runtime.stop()).completed
            restored = create_runtime(harness.settings, MetricsHost(harness.config), harness.apps)
            async with restored.running():
                reopened = await restored.chat.open_session(
                    PRINCIPAL, app_id='metrics', agent='dashboard',
                    context_ref=reference(str(scope.id)), session_key='metrics.publication-recovery',
                )
                assert reopened.session_id == session.session_id
                repeated = await restored.chat.message(PRINCIPAL, request)
                assert repeated.run_id == run.run_id and repeated.status == 'succeeded'
                assert (await restored.approvals.get(PRINCIPAL, approval.approval_id)).state == 'consumed'
                assert await run_sync(AiChartPublication.objects.count) == 1
                assert importer.call_count == 1
                assert len(endpoint.requests) == 4
            assert (await restored.stop()).completed


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize(('profile_id', 'provider_id', 'series'), [
    ('chiplet-2a-jira', 'jira', 'new_critical_high'),
    ('nvu-ttl-hsdes', 'hsdes', 'new_critical'),
])
@override_settings(
    METRICS_BASIC_AUTH_USERS={'synthetic-reviewer': 'synthetic-only'},
    METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999',
)
async def test_unpublishable_profiles_share_read_tools_and_never_request_approval(
    tmp_path, profile_id, provider_id, series,
):
    from ai_host.tests.test_workbench_context_ref import page_state
    from ai_host.workbench_context import build_context_ref

    def empty_scope():
        scope = JiraScopeConfig.objects.create(name='Synthetic empty publication', jql='project = SAMPLE')
        BugTrendScopeProviderBinding.objects.create(
            scope=scope, profile_id=profile_id, provider_id=provider_id, status='explicit',
        )
        return scope.id

    scope_id = await run_sync(empty_scope)
    ref = build_context_ref(page_state(
        scope_id=str(scope_id), profile_id=profile_id, provider_id=provider_id,
        begin='2026-08-03', end='2026-08-30',
    ))
    arguments = {**ARGUMENTS, 'profile_id': profile_id, 'requested_series': [series]}
    responses = [
        MetricToolResponse('metrics.catalog', {}, 'empty-catalog'),
        MetricToolResponse('metrics.chart_workflow', arguments, 'empty-workflow'),
        MetricToolResponse('metrics.publish_chart', arguments, 'empty-publication'),
        completion('The synthetic request was not published.'),
    ]
    with scripted_model_endpoint(responses) as endpoint:
        config = replace(build_host_config(), state_dir=tmp_path, model=endpoint.model)
        harness = RuntimeHarness(build_runtime_settings(), config, (METRICS_APP,))
        runtime = create_runtime(harness.settings, MetricsHost(harness.config), harness.apps)
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            async with runtime.running():
                session = await runtime.chat.open_session(
                    PRINCIPAL, app_id='metrics', agent='dashboard', context_ref=ref,
                )
                run = await runtime.chat.message(PRINCIPAL, ChatMessageRequest(
                    session_id=session.session_id, content='Check this synthetic profile.',
                    client_message_key='unpublishable-profile',
                    deadline_at=datetime.now(UTC) + timedelta(minutes=5),
                ))
                assert (await finished_run(runtime, run.run_id)).status == 'succeeded'
                assert await runtime.approvals.list_pending(PRINCIPAL, app_id='metrics', limit=10) == ()
                deadline = time.monotonic() + 10
                while not await run_sync(RuntimeAuditEvent.objects.filter(
                    category='tool_preview_declined', tool_name='metrics.publish_chart',
                ).exists):
                    assert time.monotonic() < deadline
                    await asyncio.sleep(0.02)
                assert await run_sync(AiChartPublication.objects.count) == 0
                assert len(endpoint.requests) == 4
                importer.assert_not_called()
            assert (await runtime.stop()).completed
