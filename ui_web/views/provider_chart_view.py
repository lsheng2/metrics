import json
from html import escape
from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse

from ..container import ui_web_container
from .bug_trend_view import validate_query_contract
from .graceful_template_view import GracefulTemplateView


PROVIDER_CHART_DATA_REQUIRED_BASE_PARAMS = frozenset({'profile_id', 'chart_id'})
PROVIDER_CHART_DATA_OPTIONAL_PARAMS = frozenset({'provider_id', 'space_id', 'release_target', 'milestone', 'chart_version', 'fact_snapshot_id', 'range_mode', 'begin_ww', 'end_ww', 'begin_date', 'end_date'})
PROVIDER_CHART_EVIDENCE_REQUIRED_BASE_PARAMS = frozenset({'profile_id', 'run', 'chart_id'})
PROVIDER_CHART_EVIDENCE_OPTIONAL_PARAMS = frozenset({'provider_id', 'bucket', 'series', 'fact_snapshot_id', 'chart_version', 'owner', 'status', 'severity', 'component', 'text', 'range_mode', 'begin_ww', 'end_ww', 'begin_date', 'end_date'})
PROVIDER_PROFILE_READINESS_REQUIRED_PARAMS = frozenset({'profile_id'})
PROVIDER_PROFILE_READINESS_OPTIONAL_PARAMS = frozenset({'provider_id', 'range_mode', 'begin_ww', 'end_ww', 'begin_date', 'end_date'})


class ProviderChartDataApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, provider_chart_data_required_params(request), PROVIDER_CHART_DATA_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            payload = self.bug_trend_facade.get_provider_chart_payload(
                provider_id=request.GET.get('provider_id'),
                profile_id=request.GET.get('profile_id'),
                begin_ww=request.GET.get('begin_ww', ''),
                end_ww=request.GET.get('end_ww', ''),
                chart_id=request.GET.get('chart_id'),
                chart_version=self._chart_version(),
                fact_snapshot_id=request.GET.get('fact_snapshot_id', ''),
                range_mode=request.GET.get('range_mode', 'ww'),
                begin_date=request.GET.get('begin_date', ''),
                end_date=request.GET.get('end_date', ''),
            )
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        return JsonResponse(payload)

    def _chart_version(self):
        raw_value = self.request.GET.get('chart_version') or '1'
        try:
            return int(raw_value)
        except ValueError:
            raise ValueError('chart_version must be an integer.')


class ProviderProfileReadinessApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, PROVIDER_PROFILE_READINESS_REQUIRED_PARAMS, PROVIDER_PROFILE_READINESS_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            payload = self.bug_trend_facade.get_provider_profile_readiness_payload(
                provider_id=request.GET.get('provider_id'),
                profile_id=request.GET.get('profile_id'),
                range_mode=request.GET.get('range_mode', 'ww'),
                begin_ww=request.GET.get('begin_ww', ''),
                end_ww=request.GET.get('end_ww', ''),
                begin_date=request.GET.get('begin_date', ''),
                end_date=request.GET.get('end_date', ''),
            )
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        return JsonResponse(payload)


class ProviderProfileAlignDashboardRangeApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, PROVIDER_PROFILE_READINESS_REQUIRED_PARAMS, PROVIDER_PROFILE_READINESS_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            dashboard_url = self.bug_trend_facade.get_provider_profile_time_range_action_url(
                provider_id=request.GET.get('provider_id'),
                profile_id=request.GET.get('profile_id'),
                range_mode=request.GET.get('range_mode', 'ww'),
                begin_ww=request.GET.get('begin_ww', ''),
                end_ww=request.GET.get('end_ww', ''),
                begin_date=request.GET.get('begin_date', ''),
                end_date=request.GET.get('end_date', ''),
            )
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        if not dashboard_url:
            return JsonResponse({'error': 'A valid range is required to align the dashboard time picker.'}, status=400)
        redirect_url = self._grafana_url(request, dashboard_url)
        escaped_url = escape(redirect_url, quote=True)
        return HttpResponse(
            f'<!doctype html><meta http-equiv="refresh" content="0;url={escaped_url}">'
            f'<script>window.location.replace({json.dumps(redirect_url)});</script>'
            f'<a href="{escaped_url}">Open aligned dashboard</a>',
            content_type='text/html',
        )

    def _grafana_url(self, request, dashboard_url):
        referer = request.META.get('HTTP_REFERER', '')
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}{dashboard_url}'
        return dashboard_url


class ProviderChartEvidenceApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, provider_chart_evidence_required_params(request), PROVIDER_CHART_EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            payload = self.bug_trend_facade.get_provider_chart_evidence_payload(
                provider_id=request.GET.get('provider_id'),
                profile_id=request.GET.get('profile_id'),
                begin_ww=request.GET.get('begin_ww', ''),
                end_ww=request.GET.get('end_ww', ''),
                chart_id=request.GET.get('chart_id'),
                chart_version=self._chart_version(),
                calculation_run_id=request.GET.get('run', ''),
                bucket_id=request.GET.get('bucket', ''),
                series_name=request.GET.get('series', ''),
                fact_snapshot_id=request.GET.get('fact_snapshot_id', ''),
                owner=request.GET.get('owner', ''),
                status=request.GET.get('status', ''),
                severity=request.GET.get('severity', ''),
                component=request.GET.get('component', ''),
                text=request.GET.get('text', ''),
                range_mode=request.GET.get('range_mode', 'ww'),
                begin_date=request.GET.get('begin_date', ''),
                end_date=request.GET.get('end_date', ''),
            )
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        return JsonResponse(payload)

    def _chart_version(self):
        raw_value = self.request.GET.get('chart_version') or '1'
        try:
            return int(raw_value)
        except ValueError:
            raise ValueError('chart_version must be an integer.')


def provider_chart_data_required_params(request):
    return PROVIDER_CHART_DATA_REQUIRED_BASE_PARAMS | provider_chart_range_required_params(request)


def provider_chart_evidence_required_params(request):
    return PROVIDER_CHART_EVIDENCE_REQUIRED_BASE_PARAMS | provider_chart_range_required_params(request)


def provider_chart_range_required_params(request):
    if request.GET.get('range_mode', 'ww').strip().lower() == 'date':
        return frozenset({'begin_date', 'end_date'})
    return frozenset({'begin_ww', 'end_ww'})
