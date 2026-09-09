from django.conf import settings

from .container import ui_web_container
from .ai_base_workbench_adapter import AiBaseWorkbenchAdapter
from .workbench_service_status import DEFAULT_FULL_STACK_LAUNCHER_COMMAND, WorkbenchServiceStatusBuilder


def member_groups(request):
    if request.headers.get('HX-Request'):
        return {}
    
    try:
        tasks_facade = ui_web_container.tasks_facade
        available_member_groups = tasks_facade.get_available_member_groups()
        return {
            'global_available_member_groups': available_member_groups
        }
    except Exception:
        return {
            'global_available_member_groups': []
        }


def service_status_bar(request):
    if request.headers.get('HX-Request'):
        return {}

    try:
        ai_adapter = AiBaseWorkbenchAdapter(DEFAULT_FULL_STACK_LAUNCHER_COMMAND)
        sidecar_status = _sidecar_status_for_status_bar(request)
        return {
            'global_service_statuses': WorkbenchServiceStatusBuilder(ai_adapter, '/').build(sidecar_status)
        }
    except Exception:
        return {
            'global_service_statuses': []
        }


def _sidecar_status_for_status_bar(request) -> dict:
    if request.resolver_match and request.resolver_match.url_name == 'workbench':
        try:
            return ui_web_container.bug_trend_facade.get_ai_sidecar_status_payload()
        except Exception:
            return _configured_sidecar_status('unavailable')
    if bool(getattr(settings, 'METRICS_AI_SIDECAR_ENABLED', False)):
        return _configured_sidecar_status('configured')
    return _configured_sidecar_status('disabled')


def _configured_sidecar_status(status: str) -> dict:
    return {
        'enabled': bool(getattr(settings, 'METRICS_AI_SIDECAR_ENABLED', False)),
        'status': status,
        'reason': '',
        'base_url': str(getattr(settings, 'METRICS_AI_BASE_URL', 'http://127.0.0.1:48300')).rstrip('/'),
        'service_id': str(getattr(settings, 'METRICS_AI_BASE_SERVICE_ID', 'dashboard-query-agent-app-service')),
        'profile_id': str(getattr(settings, 'METRICS_AI_BASE_PROFILE_ID', 'dashboard_query_agent')),
        'handshake_path': str(getattr(settings, 'METRICS_AI_BASE_HANDSHAKE_PATH', '/health/handshake')),
        'capabilities': {},
    }
