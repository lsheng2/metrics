from datetime import date, timedelta

from django.http import JsonResponse

from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


CHART_DATA_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end'})
CHART_DATA_OPTIONAL_PARAMS = frozenset()
EVIDENCE_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'run'})
EVIDENCE_OPTIONAL_PARAMS = frozenset({'bucket', 'series', 'owner', 'status', 'severity', 'component', 'text'})


def validate_query_contract(request, required_params, optional_params):
    provided_params = set(request.GET.keys())
    missing_params = sorted(param for param in required_params if not request.GET.get(param))
    unknown_params = sorted(provided_params - required_params - optional_params)
    if missing_params or unknown_params:
        return JsonResponse({
            'error': 'Invalid Bug Trend API query parameters.',
            'missing_params': missing_params,
            'unknown_params': unknown_params,
        }, status=400)
    return None


class BugTrendView(GracefulTemplateView):
    template_name = 'bug_trend.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['partials/bug_trend_content.html']
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        self._populate_common_context(context)
        scope_options = context['scope_options']
        if not scope_options:
            context['chart_json'] = '{}'
            context['selected_scope_id'] = ''
            context['unavailable_reason'] = 'Create a saved Jira scope before opening the bug trend dashboard.'
            return

        selected_scope_id = int(self.request.GET.get('scope_id') or scope_options[0].id)
        begin, end = self._date_range()
        chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end)
        evidence = None
        if chart_data.current_evidence_available:
            evidence = self.bug_trend_facade.get_evidence_data(selected_scope_id, begin, end, calculation_run_id=chart_data.calculation_run_id)
        context['selected_scope_id'] = selected_scope_id
        context['begin'] = begin.isoformat()
        context['end'] = end.isoformat()
        context['chart_json'] = self.bug_trend_facade.get_chart_json(chart_data)
        context['unavailable_reason'] = chart_data.unavailable_reason
        context['run_metadata'] = chart_data.run_metadata or {}
        context['evidence'] = evidence

    def _populate_common_context(self, context):
        context['scope_options'] = self.bug_trend_facade.get_scope_options()
        context['build_page_title'] = 'Bug Trend Indicator'

    def _date_range(self):
        today = date.today()
        default_begin = today - timedelta(days=27)
        begin = date.fromisoformat(self.request.GET.get('begin') or default_begin.isoformat())
        end = date.fromisoformat(self.request.GET.get('end') or today.isoformat())
        return begin, end


class BugTrendEvidenceView(GracefulTemplateView):
    template_name = 'partials/bug_trend_evidence.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def populate_context(self, context, **kwargs):
        begin, end = self._date_range()
        evidence = self.bug_trend_facade.get_evidence_data(
            scope_id=int(self.request.GET.get('scope_id')),
            begin=begin,
            end=end,
            calculation_run_id=self.request.GET.get('run', ''),
            bucket_id=self.request.GET.get('bucket', ''),
            series_name=self.request.GET.get('series', ''),
            owner=self.request.GET.get('owner', ''),
            status=self.request.GET.get('status', ''),
            severity=self.request.GET.get('severity', ''),
            component=self.request.GET.get('component', ''),
            text=self.request.GET.get('text', ''),
        )
        context['evidence'] = evidence

    def _date_range(self):
        begin = date.fromisoformat(self.request.GET.get('begin'))
        end = date.fromisoformat(self.request.GET.get('end'))
        return begin, end


class BugTrendChartDataApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, CHART_DATA_REQUIRED_PARAMS, CHART_DATA_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        begin, end = self._date_range()
        chart_data = self.bug_trend_facade.get_chart_data(int(request.GET.get('scope_id')), begin, end)
        return JsonResponse(self.bug_trend_facade.get_chart_payload(chart_data))

    def _date_range(self):
        begin = date.fromisoformat(self.request.GET.get('begin'))
        end = date.fromisoformat(self.request.GET.get('end'))
        return begin, end


class BugTrendEvidenceApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        begin, end = self._date_range()
        evidence = self.bug_trend_facade.get_evidence_data(
            scope_id=int(request.GET.get('scope_id')),
            begin=begin,
            end=end,
            calculation_run_id=request.GET.get('run', ''),
            bucket_id=request.GET.get('bucket', ''),
            series_name=request.GET.get('series', ''),
            owner=request.GET.get('owner', ''),
            status=request.GET.get('status', ''),
            severity=request.GET.get('severity', ''),
            component=request.GET.get('component', ''),
            text=request.GET.get('text', ''),
        )
        return JsonResponse(self.bug_trend_facade.get_evidence_payload(evidence))

    def _date_range(self):
        begin = date.fromisoformat(self.request.GET.get('begin'))
        end = date.fromisoformat(self.request.GET.get('end'))
        return begin, end
