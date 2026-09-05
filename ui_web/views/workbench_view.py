from dataclasses import replace
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import TemplateView
from django.urls import reverse

from ..container import ui_web_container
from ..ai_base_workbench_adapter import AiBaseWorkbenchAdapter
from ..workbench_grafana import grafana_full_dashboard_url, grafana_panel_embed_url
from ..workbench_registry import WorkbenchServiceStatus, default_workbench_panes
from ..workbench_state import WorkbenchPageQueryState
from .bug_trend_view import parse_date_query
from .graceful_template_view import GracefulTemplateView


class WorkbenchView(GracefulTemplateView):
    template_name = 'workbench.html'
    full_stack_launcher_command = 'powershell -ExecutionPolicy Bypass -File scripts\\e2e_dashboard_ai_stack.ps1 -Action restart -ForceByPort'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade
        self.ai_adapter = AiBaseWorkbenchAdapter(self.full_stack_launcher_command)

    def populate_context(self, context, **kwargs):
        sidecar_status = self.bug_trend_facade.get_ai_sidecar_status_payload()
        state = self._state()
        context['build_page_title'] = 'Metrics Workbench'
        context['workbench_panes'] = self._pane_registry()
        context['workbench_service_statuses'] = self._service_statuses(sidecar_status)
        context['workbench_state'] = state
        context['workbench_chart_query'] = state.chart_query_params()
        context['workbench_evidence_query'] = state.evidence_query_params()
        context['workbench_selection_error'] = state.selection_validation_error()
        context['workbench_clear_selection_url'] = self._workbench_url(state.cleared_selection().to_query_params())
        context['workbench_grafana_panel_url'] = grafana_panel_embed_url(state)
        context['workbench_grafana_full_url'] = grafana_full_dashboard_url(state)
        context['workbench_ai_context'] = self._ai_context(state, sidecar_status)
        self._populate_chart_context(context, state)

    def _pane_registry(self):
        return [
            pane.to_dict(self._target_url(pane.target_route))
            for pane in default_workbench_panes()
        ]

    def _target_url(self, route_name: str) -> str:
        return reverse(route_name)

    def _workbench_url(self, params: dict) -> str:
        query = urlencode(params)
        if query:
            return f'{reverse("ui_web:workbench")}?{query}'
        return reverse('ui_web:workbench')

    def _service_statuses(self, sidecar_status: dict) -> list[WorkbenchServiceStatus]:
        ai_status = sidecar_status.get('status') or 'disabled'
        grafana_base_url = str(settings.METRICS_AI_GRAFANA_BASE_URL or '').rstrip('/')
        grafana_status = 'configured' if grafana_base_url else 'unavailable'
        ai_frontend_url = self.ai_adapter.frontend_base_url(sidecar_status)
        checked_at = datetime.now().strftime('%H:%M:%S')
        return [
            WorkbenchServiceStatus(
                'dashboard',
                'Dashboard',
                'available',
                reverse('ui_web:homepage'),
                next_action='If this shell stops responding, restart python manage.py runserver on the Dashboard port.',
                checked_at=checked_at,
            ),
            WorkbenchServiceStatus(
                'grafana',
                'Grafana',
                grafana_status,
                grafana_base_url,
                '' if grafana_base_url else 'METRICS_AI_GRAFANA_BASE_URL is empty.',
                self._grafana_next_action(grafana_base_url),
                checked_at,
            ),
            WorkbenchServiceStatus(
                'ai-base',
                'AI Base',
                ai_status,
                ai_frontend_url,
                str(sidecar_status.get('reason') or ''),
                self.ai_adapter.next_action(ai_status),
                checked_at,
            ),
        ]

    def _grafana_next_action(self, grafana_base_url: str) -> str:
        if not grafana_base_url:
            return 'Set METRICS_AI_GRAFANA_BASE_URL and start the Grafana service before using the panel preview.'
        port = urlparse(grafana_base_url).port
        if port:
            return f'If the panel is blank, check that Grafana is listening on port {port}.'
        return 'If the panel is blank, check the configured Grafana URL and service health.'

    def _state(self) -> WorkbenchPageQueryState:
        state = WorkbenchPageQueryState.from_query(self.request.GET)
        today = date.today()
        scope_options = self.bug_trend_facade.get_scope_options()
        scope_id = state.scope_id or self._default_scope_id(state.profile_id, scope_options)
        scope_option = self._scope_option(scope_options, scope_id)
        profile_id = scope_option.profile_id if scope_option and scope_option.profile_id else state.profile_id
        provider_id = scope_option.provider_id if scope_option and scope_option.provider_id else self._provider_id_for_profile(profile_id) or state.provider_id
        return replace(
            state,
            scope_id=scope_id,
            profile_id=profile_id,
            provider_id=provider_id,
            begin=state.begin or (today - timedelta(days=27)).isoformat(),
            end=state.end or today.isoformat(),
        )

    def _default_scope_id(self, profile_id: str, scope_options=None) -> str:
        scope_options = scope_options if scope_options is not None else self.bug_trend_facade.get_scope_options()
        if not scope_options:
            return ''
        normalized_profile_id = profile_id.lower()
        for scope in scope_options:
            if scope.name.lower() == normalized_profile_id:
                return str(scope.id)
        return str(scope_options[0].id)

    def _scope_option(self, scope_options, scope_id: str):
        if not scope_id:
            return None
        return next((scope for scope in scope_options if str(scope.id) == str(scope_id)), None)

    def _provider_id_for_profile(self, profile_id: str) -> str:
        if not profile_id:
            return ''
        try:
            readiness = self.bug_trend_facade.get_provider_profile_readiness_payload('', profile_id)
        except Exception:
            return self._fallback_provider_id_for_profile(profile_id)
        return str(readiness.get('provider_id') or '') or self._fallback_provider_id_for_profile(profile_id)

    def _fallback_provider_id_for_profile(self, profile_id: str) -> str:
        normalized_profile = profile_id.lower()
        if 'hsdes' in normalized_profile:
            return 'hsdes'
        if 'jira' in normalized_profile:
            return 'jira'
        return ''

    def _populate_chart_context(self, context, state: WorkbenchPageQueryState):
        scope_options = self.bug_trend_facade.get_scope_options()
        chart_options = self.bug_trend_facade.get_chart_options()
        context['scope_options'] = scope_options
        context['chart_options'] = chart_options
        context['active_chart_id'] = state.chart_id or 'default_bug_trend'
        active_chart = self._active_chart_option(chart_options, context['active_chart_id'])
        context['workbench_evidence_capability'] = active_chart.capability if active_chart else 'unsupported'
        context['workbench_evidence_unavailable_reason'] = ''
        if not scope_options:
            context['selected_scope_id'] = ''
            context['chart_json'] = '{}'
            context['unavailable_reason'] = 'Create a saved Jira scope before opening the workbench chart pane.'
            context['run_metadata'] = {}
            return

        selected_scope_id = int(state.scope_id)
        begin = parse_date_query(state.begin, 'begin')
        end = parse_date_query(state.end, 'end')
        try:
            chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end, context['active_chart_id'])
        except ObjectDoesNotExist:
            context['active_chart_id'] = 'default_bug_trend'
            chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end, context['active_chart_id'])
        context['selected_scope_id'] = selected_scope_id
        context['begin'] = begin.isoformat()
        context['end'] = end.isoformat()
        context['chart_json'] = self.bug_trend_facade.get_chart_json(chart_data)
        context['unavailable_reason'] = chart_data.unavailable_reason
        context['run_metadata'] = chart_data.run_metadata or {}
        context['evidence'] = None
        if context['workbench_evidence_capability'] == 'summary_only':
            context['workbench_evidence_unavailable_reason'] = (
                active_chart.unsupported_reason or 'Selected chart does not support ticket-level evidence.'
            )
            return
        if context['workbench_evidence_capability'] == 'unsupported':
            context['workbench_evidence_unavailable_reason'] = 'Selected chart does not expose ticket-level evidence.'
            return
        if chart_data.current_evidence_available and not context['workbench_selection_error']:
            context['evidence'] = self.bug_trend_facade.get_evidence_data(
                selected_scope_id,
                begin,
                end,
                calculation_run_id=state.calculation_run_id or chart_data.calculation_run_id,
                bucket_id=state.selected_bucket_id,
                series_name=state.selected_series_name,
                owner=state.list_filters.owner,
                status=state.list_filters.status,
                severity=state.list_filters.severity,
                component=state.list_filters.component,
                text=state.list_filters.text,
                active_chart_id=context['active_chart_id'],
            )

    def _active_chart_option(self, chart_options, chart_id):
        return next((chart for chart in chart_options if chart.chart_id == chart_id), None)

    def _ai_context(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> dict:
        return self.ai_adapter.context(state, sidecar_status)


class WorkbenchGrafanaSelectionView(TemplateView):
    template_name = 'workbench_grafana_selection.html'
