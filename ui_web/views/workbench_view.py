from dataclasses import replace
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.parse import urlparse

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.urls import reverse

from ..container import ui_web_container
from ..ai_base_workbench_adapter import AiBaseWorkbenchAdapter
from ..workbench_grafana import grafana_full_dashboard_url, grafana_panel_embed_url
from ..workbench_registry import default_workbench_panes
from ..workbench_service_status import WorkbenchServiceStatusBuilder
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
        context['workbench_ai_workspace_error'] = self.request.GET.get('ai_workspace_error', '')
        self._populate_chart_context(context, state)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') != 'sync_ai_workspace':
            return redirect('ui_web:workbench')
        sidecar_status = self.bug_trend_facade.get_ai_sidecar_status_payload()
        state = self._state(request.POST)
        redirect_params = state.to_query_params()
        try:
            context_bundle = self.bug_trend_facade.get_ai_workspace_context_bundle_payload(state.profile_id)
            self.ai_adapter.sync_workspace_context(sidecar_status, context_bundle)
        except Exception as error:
            redirect_params['ai_workspace_error'] = f'{type(error).__name__}'
        return redirect(self._workbench_url(redirect_params))

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

    def _service_statuses(self, sidecar_status: dict):
        return WorkbenchServiceStatusBuilder(self.ai_adapter, reverse('ui_web:homepage')).build(sidecar_status)

    def _state(self, query=None) -> WorkbenchPageQueryState:
        state = WorkbenchPageQueryState.from_query(query or self.request.GET)
        today = date.today()
        scope_options = self.bug_trend_facade.get_scope_options()
        scope_id = state.scope_id or self._default_scope_id(state.profile_id, scope_options)
        scope_option = self._scope_option(scope_options, scope_id)
        if scope_option and scope_option.binding_status in {'explicit', 'compatibility'}:
            profile_id = scope_option.profile_id
            provider_id = scope_option.provider_id
        elif scope_option:
            profile_id = ''
            provider_id = ''
        else:
            profile_id = state.profile_id
            provider_id = self._provider_id_for_profile(profile_id) or state.provider_id
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
        active_scope = self._scope_option(scope_options, state.scope_id)
        context['workbench_binding_unavailable_reason'] = self._binding_unavailable_reason(active_scope)
        context['workbench_binding_warning'] = self._binding_warning(active_scope)
        active_chart = self._active_chart_option(chart_options, context['active_chart_id'])
        context['workbench_evidence_capability'] = active_chart.capability if active_chart else 'unsupported'
        context['workbench_evidence_unavailable_reason'] = ''
        if not scope_options:
            context['selected_scope_id'] = ''
            context['chart_json'] = '{}'
            context['unavailable_reason'] = 'Create a scope before opening the workbench chart pane.'
            context['run_metadata'] = {}
            return
        if context['workbench_binding_unavailable_reason']:
            context['selected_scope_id'] = int(state.scope_id)
            context['chart_json'] = '{}'
            context['unavailable_reason'] = context['workbench_binding_unavailable_reason']
            context['run_metadata'] = {}
            context['evidence'] = None
            context['workbench_evidence_unavailable_reason'] = context['workbench_binding_unavailable_reason']
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

    def _binding_unavailable_reason(self, scope_option) -> str:
        if not scope_option:
            return ''
        if scope_option.binding_status in {'explicit', 'compatibility'} and scope_option.profile_id and scope_option.provider_id:
            return ''
        if scope_option.binding_status == 'disabled':
            return 'Selected scope is disabled. Enable or repair it in Scope Library before using provider-backed panes.'
        if scope_option.binding_blockers:
            return scope_option.binding_blockers[0].get('message', 'Scope is not bound to a provider profile.')
        return 'Scope is not bound to a provider profile.'

    def _binding_warning(self, scope_option) -> str:
        if not scope_option:
            return ''
        if scope_option.binding_status == 'compatibility':
            return 'This scope is using a compatibility provider binding. Confirm it in Scope Library before explicit-only operation.'
        return ''

    def _ai_context(self, state: WorkbenchPageQueryState, sidecar_status: dict) -> dict:
        context = self.ai_adapter.context(state, sidecar_status, self._host_origin())
        scope_binding = self._scope_binding_context(state)
        context['scope_binding'] = scope_binding
        context['ai_base']['chat_gate'] = self._ai_chat_gate(state, sidecar_status, scope_binding)
        context['ai_base']['chat_ready'] = context['ai_base']['chat_gate']['ready']
        return context

    def _scope_binding_context(self, state: WorkbenchPageQueryState) -> dict:
        scope_option = self._scope_option(self.bug_trend_facade.get_scope_options(), state.scope_id)
        if not scope_option:
            if state.profile_id and state.provider_id:
                return {
                    'status': 'explicit',
                    'profile_id': state.profile_id,
                    'provider_id': state.provider_id,
                    'blockers': [],
                }
            return {
                'status': 'configuration_required',
                'profile_id': '',
                'provider_id': '',
                'blockers': [{'message': 'Scope is not bound to a provider profile.'}],
            }
        return {
            'status': scope_option.binding_status,
            'profile_id': scope_option.profile_id,
            'provider_id': scope_option.provider_id,
            'blockers': scope_option.binding_blockers or [],
        }

    def _ai_chat_gate(self, state: WorkbenchPageQueryState, sidecar_status: dict, scope_binding: dict) -> dict:
        if not self.ai_adapter.is_enabled(sidecar_status):
            return {
                'ready': False,
                'status': 'disabled',
                'message': 'AI chat is not enabled for this Dashboard process.',
                'can_sync_workspace': False,
            }
        if self._scope_binding_needs_registry_profile(scope_binding):
            return {
                'ready': False,
                'status': 'registry_profile_required',
                'message': self._registry_profile_required_message(scope_binding),
                'can_sync_workspace': False,
            }
        if scope_binding['status'] not in {'explicit', 'compatibility'} or not state.profile_id or not state.provider_id:
            return {
                'ready': False,
                'status': 'binding_required',
                'message': 'Bind this scope to a provider profile before opening AI chat.',
                'can_sync_workspace': False,
            }
        if not self._is_registry_backed_profile(state.profile_id, state.provider_id):
            return {
                'ready': False,
                'status': 'registry_profile_required',
                'message': 'AI chat requires a registry-backed provider profile. Rebind this scope in Scope Library.',
                'can_sync_workspace': False,
            }
        return self.ai_adapter.resolve_chat_binding(state, sidecar_status, self._host_origin())

    def _scope_binding_needs_registry_profile(self, scope_binding: dict) -> bool:
        blocker_codes = {
            blocker.get('code', '')
            for blocker in scope_binding.get('blockers', [])
            if isinstance(blocker, dict)
        }
        return bool(blocker_codes.intersection({
            'profile_not_found',
            'profile_disabled',
            'provider_profile_mismatch',
            'registered_provider_profile_required',
        }))

    def _registry_profile_required_message(self, scope_binding: dict) -> str:
        blockers = [
            blocker
            for blocker in scope_binding.get('blockers', [])
            if isinstance(blocker, dict) and blocker.get('message')
        ]
        blocker_message = blockers[0]['message'] if blockers else 'AI chat requires a registry-backed provider profile.'
        return f'{blocker_message} Rebind this scope in Scope Library.'

    def _is_registry_backed_profile(self, profile_id: str, provider_id: str) -> bool:
        return any(
            choice.profile_id == profile_id and choice.provider_id == provider_id
            for choice in self.bug_trend_facade.get_scope_provider_profile_choices()
        )

    def _host_origin(self) -> str:
        parsed_url = urlparse(self.request.build_absolute_uri('/'))
        if not parsed_url.scheme or not parsed_url.netloc:
            return ''
        return f'{parsed_url.scheme}://{parsed_url.netloc}'


class WorkbenchGrafanaSelectionView(TemplateView):
    template_name = 'workbench_grafana_selection.html'
