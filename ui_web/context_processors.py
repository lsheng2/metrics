from .container import ui_web_container
from .navigation import build_navigation
from .workbench_service_status import WorkbenchServiceStatusBuilder


def dashboard_navigation(request):
    if request.headers.get('HX-Request'):
        return {}

    resolver_match = getattr(request, 'resolver_match', None)
    url_name = resolver_match.url_name if resolver_match else ''
    sections, active = build_navigation(url_name or '')
    return {
        'dashboard_navigation': sections,
        'dashboard_nav_active': active,
    }


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
        return {
            'global_service_statuses': WorkbenchServiceStatusBuilder('/').build()
        }
    except Exception:
        return {
            'global_service_statuses': []
        }
