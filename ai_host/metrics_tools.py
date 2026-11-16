from datetime import date, timedelta
import json
import re

from django.urls import reverse

from ai_base_runtime.apps import PreviewDeclined, PreviewReady, ToolDefinition, ToolError
from ai_base_runtime.contracts import canonical_digest, canonical_json

from bug_metrics.app.api.ai_chart_inputs import draft_crosses_boundary
from bug_metrics.app.api.ai_publication_contracts import ApprovedChartPublication, ChartWorkflowRequest
from ai_host.context_provider import resolve_context
from ai_host.metrics_tool_schemas import CATALOG_SCHEMA, RESULT_SCHEMA, WORKFLOW_SCHEMA
from ai_host.run_sync import run_sync
from ai_host.workbench_context import valid_context_ref


def _api():
    from bug_metrics.app.api import bug_trend_api
    return bug_trend_api


def _day(value, *, end=False):
    match = re.fullmatch(r'(\d{2}|\d{4})WW(\d{2})', value, re.IGNORECASE)
    if match:
        year = int(match[1]) + (2000 if len(match[1]) == 2 else 0)
        return date.fromisocalendar(year, int(match[2]), 1) + timedelta(days=6 if end else 0)
    return date.fromisoformat(value)


async def _bound_context(context, arguments, *, workflow=False):
    ref = context.context_ref
    if ref is None:
        return {
            'status': 'scope_required', 'next_action': 'open_workbench',
            'url': reverse('ui_web:workbench'),
        }
    if not valid_context_ref(ref):
        raise ToolError('context_boundary_violation')
    values = ref.values
    if arguments.get('profile_id', values['profile_id']) != values['profile_id']:
        raise ToolError('context_boundary_violation')
    if workflow:
        try:
            start, end = _day(arguments['range_start']), _day(arguments['range_end'], end=True)
            if start < _day(values['begin']) or end > _day(values['end'], end=True) or start > end:
                raise ValueError()
            if draft_crosses_boundary(
                arguments.get('render_config'), profile_id=values['profile_id'],
                provider_id=values['provider_id'], scope_id=values['binding_key'].rsplit('.', 1)[-1],
            ):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise ToolError('context_boundary_violation') from None
    bundle = await resolve_context(context.principal, ref)
    return bundle if bundle['status'] != 'ready' else None


async def catalog_handler(context, arguments):
    error = await _bound_context(context, arguments)
    if error is not None:
        return error
    catalog = await run_sync(
        _api().list_ai_dashboard_composition_catalog, context.context_ref.values['profile_id'],
    )
    return {'status': 'catalog', 'catalog': catalog}


async def chart_workflow_handler(context, arguments):
    plain = json.loads(canonical_json(arguments))
    error = await _bound_context(context, plain, workflow=True)
    if error is not None:
        return error
    request = ChartWorkflowRequest(**plain)
    return await run_sync(_api().evaluate_ai_chart_workflow, request)


async def publish_preview(context, arguments):
    plain = json.loads(canonical_json(arguments))
    error = await _bound_context(context, plain, workflow=True)
    if error is not None:
        return PreviewDeclined(result=error)
    request = ChartWorkflowRequest(**plain)
    preview = await run_sync(_api().preview_ai_chart_publication, request)
    if not preview.ready:
        return PreviewDeclined(result=preview.workflow)
    return PreviewReady(content=preview.content)


async def publish_handler(context, arguments):
    approval = context.approval
    if approval is None:
        raise ToolError()
    try:
        content = json.loads(approval.preview)
        if canonical_digest(content) != approval.preview_digest:
            raise ValueError()
    except (TypeError, ValueError):
        raise ToolError('preview_digest_mismatch') from None
    approved = ApprovedChartPublication(
        preview_bytes=approval.preview, preview_digest=approval.preview_digest,
        approval_id=approval.approval_id, tool_call_id=context.tool_call_id,
        run_id=context.run_id, decided_by=approval.decided_by.id, decided_at=approval.decided_at,
    )
    return await run_sync(_api().publish_approved_ai_chart, approved)


METRICS_TOOLS = (
    ToolDefinition(
        name='metrics.catalog', effect='read', requires_approval=False,
        input_schema=CATALOG_SCHEMA, result_schema=RESULT_SCHEMA,
        implementation_version='1', handler=catalog_handler,
    ),
    ToolDefinition(
        name='metrics.chart_workflow', effect='read', requires_approval=False,
        input_schema=WORKFLOW_SCHEMA, result_schema=RESULT_SCHEMA,
        implementation_version='1', handler=chart_workflow_handler,
    ),
    ToolDefinition(
        name='metrics.publish_chart', effect='external', requires_approval=True,
        input_schema=WORKFLOW_SCHEMA, result_schema=RESULT_SCHEMA,
        implementation_version='1', handler=publish_handler, preview=publish_preview,
    ),
)
