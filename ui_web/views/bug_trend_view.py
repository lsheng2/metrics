from datetime import date, timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect

from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


CHART_DATA_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'chart_id'})
CHART_DATA_OPTIONAL_PARAMS = frozenset()
EVIDENCE_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'run', 'chart_id'})
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


def chart_id_error_response(error):
    if isinstance(error, ObjectDoesNotExist):
        return JsonResponse({'error': 'Unknown or unpublished Bug Trend chart.', 'chart_id': ''}, status=400)
    if isinstance(error, ValueError):
        return JsonResponse({'error': str(error)}, status=400)
    return None


def parse_date_query(value: str, field_name: str):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{field_name} must be an ISO date.')


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
        active_chart_id = self.request.GET.get('chart_id') or 'default_bug_trend'
        active_chart = self._active_chart_option(context['chart_options'], active_chart_id)
        begin, end = self._date_range()
        try:
            chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end, active_chart_id)
        except ObjectDoesNotExist:
            active_chart_id = 'default_bug_trend'
            active_chart = self._active_chart_option(context['chart_options'], active_chart_id)
            chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end, active_chart_id)
        evidence = None
        evidence_unavailable_reason = ''
        if active_chart and active_chart.capability == 'summary_only':
            evidence_unavailable_reason = active_chart.unsupported_reason or 'Selected chart does not support ticket evidence.'
        elif chart_data.current_evidence_available:
            evidence = self.bug_trend_facade.get_evidence_data(selected_scope_id, begin, end, calculation_run_id=chart_data.calculation_run_id, active_chart_id=active_chart_id)
        context['selected_scope_id'] = selected_scope_id
        context['active_chart_id'] = active_chart_id
        context['begin'] = begin.isoformat()
        context['end'] = end.isoformat()
        context['chart_json'] = self.bug_trend_facade.get_chart_json(chart_data)
        context['unavailable_reason'] = chart_data.unavailable_reason
        context['run_metadata'] = chart_data.run_metadata or {}
        context['evidence'] = evidence
        context['evidence_unavailable_reason'] = evidence_unavailable_reason

    def _populate_common_context(self, context):
        context['scope_options'] = self.bug_trend_facade.get_scope_options()
        context['chart_options'] = self.bug_trend_facade.get_chart_options()
        context['build_page_title'] = 'Bug Trend Indicator'

    def _date_range(self):
        today = date.today()
        default_begin = today - timedelta(days=27)
        begin = parse_date_query(self.request.GET.get('begin') or default_begin.isoformat(), 'begin')
        end = parse_date_query(self.request.GET.get('end') or today.isoformat(), 'end')
        return begin, end

    def _active_chart_option(self, chart_options, chart_id):
        return next((chart for chart in chart_options if chart.chart_id == chart_id), None)


class BugTrendEvidenceView(GracefulTemplateView):
    template_name = 'partials/bug_trend_evidence.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        return super().get(request, *args, **kwargs)

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
            active_chart_id=self.request.GET.get('chart_id'),
        )
        context['evidence'] = evidence

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end


class BugTrendEvidenceExportView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            begin, end = self._date_range()
            export = self.bug_trend_facade.export_evidence_data(
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
                active_chart_id=request.GET.get('chart_id'),
            )
        except (ObjectDoesNotExist, ValueError) as error:
            return chart_id_error_response(error)
        response = HttpResponse(export.content, content_type=export.content_type)
        response['Content-Disposition'] = f'attachment; filename="{export.filename}"'
        return response

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end


class BugTrendScopeAuditView(GracefulTemplateView):
    template_name = 'bug_trend_scope_audit.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def populate_context(self, context, **kwargs):
        audit = self.bug_trend_facade.get_scope_audit_data(int(self.request.GET.get('scope_id')))
        context['audit'] = audit
        context['build_page_title'] = 'Bug Trend Scope Audit'


class BugTrendScopeConfigView(GracefulTemplateView):
    template_name = 'bug_trend_scope_config.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            saved, hash_changed = self.bug_trend_facade.save_scope_config(request.POST)
        except ValueError as error:
            context = self.get_context_data(**kwargs)
            context['config'] = self.bug_trend_facade.scope_config_from_post(request.POST)
            context['scope_config_errors'] = error.args[0] if error.args else {'config': 'Invalid scope config.'}
            return self.render_to_response(context, status=400)
        response = redirect('ui_web:bug_trend_scope_config')
        response['Location'] = f'{response["Location"]}?scope_id={saved.id}&saved=1&hash_changed={int(hash_changed)}'
        return response

    def populate_context(self, context, **kwargs):
        scope_id = self.request.GET.get('scope_id')
        if not scope_id or not scope_id.isdecimal():
            context['config'] = None
            context['scope_config_errors'] = {'scope_id': 'A valid scope id is required.'}
            context['build_page_title'] = 'Bug Trend Scope Config'
            return
        config = self.bug_trend_facade.get_scope_config(
            int(scope_id),
            self.request.GET.get('add_field', ''),
            self.request.GET.get('add_value', ''),
        )
        context['config'] = config
        context['saved'] = self.request.GET.get('saved') == '1'
        context['hash_changed'] = self.request.GET.get('hash_changed') == '1'
        context['build_page_title'] = 'Bug Trend Scope Config'

    def render_to_response(self, context, **response_kwargs):
        if context.get('scope_config_errors') and context.get('config') is None:
            response_kwargs.setdefault('status', 400)
        return super().render_to_response(context, **response_kwargs)


class BugTrendChartDataApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, CHART_DATA_REQUIRED_PARAMS, CHART_DATA_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            begin, end = self._date_range()
            chart_data = self.bug_trend_facade.get_chart_data(int(request.GET.get('scope_id')), begin, end, request.GET.get('chart_id'))
        except (ObjectDoesNotExist, ValueError) as error:
            return chart_id_error_response(error)
        return JsonResponse(self.bug_trend_facade.get_chart_payload(chart_data))

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end


class BugTrendEvidenceApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, EVIDENCE_REQUIRED_PARAMS, EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
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
                active_chart_id=request.GET.get('chart_id'),
            )
        except (ObjectDoesNotExist, ValueError) as error:
            return chart_id_error_response(error)
        return JsonResponse(self.bug_trend_facade.get_evidence_payload(evidence))

    def _date_range(self):
        begin = parse_date_query(self.request.GET.get('begin'), 'begin')
        end = parse_date_query(self.request.GET.get('end'), 'end')
        return begin, end
