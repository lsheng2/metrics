from django.conf import settings
from django.urls import reverse

from ai_base_runtime.apps import ContextProvider, ToolError
from ai_base_runtime.spi import Principal

from ai_host.run_sync import run_sync
from ai_host.workbench_context import CONTEXT_KIND, valid_context_ref


def _check_principal(principal):
    if not isinstance(principal, Principal):
        raise ToolError('context_boundary_violation')
    users = settings.METRICS_BASIC_AUTH_USERS
    if users is None:
        valid = principal.id == 'local_operator' and principal.anonymous
    else:
        valid = isinstance(users, dict) and principal.id in users and not principal.anonymous
    if not valid:
        raise ToolError('context_boundary_violation')


def _resolve(principal, ref):
    _check_principal(principal)
    if not valid_context_ref(ref):
        raise ToolError('context_boundary_violation')
    from bug_metrics.app.api import bug_trend_api

    bundle = bug_trend_api.get_ai_workbench_context(dict(ref.values))
    if bundle['status'] == 'binding_unresolved':
        return {'status': 'binding_unresolved', 'repair_url': reverse('ui_web:bug_trend_scope_library')}
    return bundle


async def validate_context(principal, ref):
    bundle = await run_sync(_resolve, principal, ref)
    if bundle['status'] != 'ready':
        raise ToolError('context_boundary_violation')


async def resolve_context(principal, ref):
    return await run_sync(_resolve, principal, ref)


WORKBENCH_CONTEXT_PROVIDER = ContextProvider(
    kind=CONTEXT_KIND, validate=validate_context, resolve=resolve_context,
)
