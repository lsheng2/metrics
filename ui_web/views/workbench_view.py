from dataclasses import replace
from datetime import date, timedelta
from urllib.parse import urlencode

from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import TemplateView
from django.urls import reverse

from ..container import ui_web_container
from ai_host.pane import workbench_pane
from ..workbench_grafana import grafana_full_dashboard_url, grafana_panel_embed_url
from ..workbench_registry import default_workbench_panes
from ..workbench_state import WorkbenchPageQueryState
from .bug_trend_query import parse_date_query
from .graceful_template_view import GracefulTemplateView


class WorkbenchView(GracefulTemplateView):
    template_name = 'workbench.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def populate_context(self, context, **kwargs):
        state = self._state()
        context['build_page_title'] = 'Metrics Workbench'
        context['workbench_panes'] = self._pane_registry()
        context['workbench_state'] = state
        context['workbench_chart_query'] = state.chart_query_params()
        context['workbench_evidence_query'] = state.evidence_query_params()
        context['workbench_selection_error'] = state.selection_validation_error()
        context['workbench_clear_selection_url'] = self._workbench_url(state.cleared_selection().to_query_params())
        context['workbench_grafana_panel_url'] = grafana_panel_embed_url(state)
        context['workbench_grafana_full_url'] = grafana_full_dashboard_url(state)
        self._populate_chart_context(context, state)
        pane_state = replace(state, chart_id=context['active_chart_id'])
        context['workbench_ai_context'] = {
            'runtime': workbench_pane(self.request, pane_state, ticket_ids=state.selected_ticket_ids),
            'scope_binding': self._scope_binding_context(state),
        }
        context['publish_history'] = self.bug_trend_facade.get_ai_chart_publications(10)

    def _pane_registry(self):
        return [
            pane.to_dict(self._target_url(pane.target_route))
            for pane in default_workbench_panes()
        ]

    def _target_url(self, route_name: str) -> str:
        return reverse(route_name)

    def _workbench_url(self, params: dict) -> str:
        query = urlencode(params, doseq=True)
        if query:
            return f'{reverse("ui_web:workbench")}?{query}'
        return reverse('ui_web:workbench')

    def _state(self, query=None) -> WorkbenchPageQueryState:
        state = WorkbenchPageQueryState.from_query(query or self.request.GET)
        today = date.today()
        scope_options = self.bug_trend_facade.get_scope_options()
        scope_id = state.scope_id or self._default_scope_id(scope_options)
        scope_option = self._scope_option(scope_options, scope_id)
        if scope_option and scope_option.binding_status in {'explicit', 'compatibility'}:
            profile_id = scope_option.profile_id
            provider_id = scope_option.provider_id
        else:
            profile_id = ''
            provider_id = ''
        return replace(
            state,
            scope_id=scope_id,
            profile_id=profile_id,
            provider_id=provider_id,
            begin=state.begin or (today - timedelta(days=27)).isoformat(),
            end=state.end or today.isoformat(),
        )

    def _default_scope_id(self, scope_options=None) -> str:
        scope_options = scope_options if scope_options is not None else self.bug_trend_facade.get_scope_options()
        if not scope_options:
            return ''
        return str(scope_options[0].id)

    def _scope_option(self, scope_options, scope_id: str):
        if not scope_id:
            return None
        return next((scope for scope in scope_options if str(scope.id) == str(scope_id)), None)

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
        context['chart_has_data'] = bool(chart_data.labels)
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

    def _scope_binding_context(self, state: WorkbenchPageQueryState) -> dict:
        scope_option = self._scope_option(self.bug_trend_facade.get_scope_options(), state.scope_id)
        if not scope_option:
            return {
                'status': 'configuration_required',
                'profile_id': '',
                'provider_id': '',
                'blockers': [{'message': 'Select a saved scope with a provider profile binding.'}],
            }
        return {
            'status': scope_option.binding_status,
            'profile_id': scope_option.profile_id,
            'provider_id': scope_option.provider_id,
            'blockers': scope_option.binding_blockers or [],
        }

class WorkbenchGrafanaSelectionView(TemplateView):
    template_name = 'workbench_grafana_selection.html'
