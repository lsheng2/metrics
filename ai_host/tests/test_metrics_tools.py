from dataclasses import replace
from datetime import UTC, datetime
import time

import pytest
from django.test import override_settings
from jsonschema import Draft202012Validator

from ai_base_runtime.apps import PreviewDeclined, PreviewReady, ToolApproval, ToolContext, ToolError
from ai_base_runtime.spi import Principal
from ai_base_runtime.testkit import check_app_package
from ai_host.package import METRICS_APP
from ai_host.settings import build_runtime_settings
from ai_host.tests.test_workbench_context_ref import page_state
from ai_host.workbench_context import build_context_ref
from bug_metrics.tests.ai_publication_fixtures import seed_publication_data


def context(ref=None, approval=None):
    return ToolContext(
        principal=Principal(id='local_operator', display_name='Local operator', anonymous=True),
        run_id='run-1', tool_call_id='call-1', deadline=time.monotonic() + 60,
        context_ref=ref, approval=approval,
    )


def arguments(**changes):
    return {
        'profile_id': 'chiplet-2a-jira', 'chart_id': 'open_bug_trend',
        'requested_series': ['new_critical_high'],
        'range_mode': 'ww', 'range_start': '26WW32', 'range_end': '26WW35',
        **changes,
    }


def reference(scope_id='42'):
    return build_context_ref(page_state(
        scope_id=scope_id, profile_id='chiplet-2a-jira',
        begin='2026-08-03', end='2026-08-30',
    ))


def test_package_exposes_only_scoped_read_tools_and_approval_gated_publish():
    check_app_package(METRICS_APP, limits=build_runtime_settings().limits)
    tools = {tool.name: tool for tool in METRICS_APP.tools}
    assert set(tools) == {'metrics.catalog', 'metrics.chart_workflow', 'metrics.publish_chart'}
    assert tools['metrics.catalog'].effect == tools['metrics.chart_workflow'].effect == 'read'
    assert tools['metrics.publish_chart'].effect == 'external'
    assert tools['metrics.publish_chart'].requires_approval
    for name in ('metrics.chart_workflow', 'metrics.publish_chart'):
        validator = Draft202012Validator(dict(tools[name].input_schema))
        for field in ('actor', 'approval_id', 'proof_id', 'workspace_key'):
            assert not validator.is_valid(arguments(**{field: 'forged'}))


@pytest.mark.asyncio
async def test_missing_context_returns_guidance_without_accessing_metrics_data():
    from ai_host.metrics_tools import catalog_handler

    result = await catalog_handler(context(), {})
    assert result['status'] == 'scope_required'
    assert result['next_action'] == 'open_workbench'


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [
    {'profile_id': 'nvu-ttl-hsdes'},
    {'range_start': '26WW01'},
    {'render_config': {'profile_variable': 'profile_id', 'variables': [{
        'name': 'profile_id', 'kind': 'profile', 'values': ['nvu-ttl-hsdes'], 'current': 'nvu-ttl-hsdes',
    }]}},
])
async def test_out_of_scope_arguments_are_rejected_before_database_access(changes):
    from ai_host.metrics_tools import chart_workflow_handler

    with pytest.raises(ToolError) as error:
        await chart_workflow_handler(context(reference()), arguments(**changes))
    assert error.value.code == 'context_boundary_violation'


@pytest.fixture
def publication_scope():
    return seed_publication_data()[0]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@override_settings(METRICS_BASIC_AUTH_USERS=None, METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999')
async def test_real_metrics_services_back_read_tools_and_publish_preview(publication_scope):
    from ai_host.metrics_tools import catalog_handler, chart_workflow_handler, publish_preview

    ctx = context(reference(str(publication_scope.id)))
    catalog = await catalog_handler(ctx, {})
    workflow = await chart_workflow_handler(ctx, arguments())
    preview = await publish_preview(ctx, arguments())
    assert catalog['status'] == 'catalog'
    assert workflow['status'] == 'draft_validated'
    assert workflow['publish_readiness']['ready']
    assert isinstance(preview, PreviewReady)
    assert preview.content['publication']['profile_id'] == 'chiplet-2a-jira'


@pytest.mark.asyncio
async def test_publish_handler_rejects_wrong_digest_without_database_access():
    from ai_host.metrics_tools import publish_handler

    principal = context().principal
    approval = ToolApproval(
        preview=b'{}', preview_digest='0' * 64,
        decided_by=principal, decided_at=datetime(2026, 11, 16, tzinfo=UTC),
    )
    with pytest.raises(ToolError) as error:
        await publish_handler(context(approval=approval), arguments())
    assert error.value.code == 'preview_digest_mismatch'
