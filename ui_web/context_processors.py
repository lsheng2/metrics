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
        sidecar_status = ui_web_container.bug_trend_facade.get_ai_sidecar_status_payload()
    except Exception:
        sidecar_status = {}

    try:
        ai_adapter = AiBaseWorkbenchAdapter(DEFAULT_FULL_STACK_LAUNCHER_COMMAND)
        return {
            'global_service_statuses': WorkbenchServiceStatusBuilder(ai_adapter, '/').build(sidecar_status)
        }
    except Exception:
        return {
            'global_service_statuses': []
        }
