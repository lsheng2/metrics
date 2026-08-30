from django.http import JsonResponse

from ..container import ui_web_container
from .bug_trend_view import validate_query_contract
from .graceful_template_view import GracefulTemplateView


PROVIDER_CHART_DATA_REQUIRED_PARAMS = frozenset({'profile_id', 'begin_ww', 'end_ww', 'chart_id'})
PROVIDER_CHART_DATA_OPTIONAL_PARAMS = frozenset({'provider_id', 'space_id', 'release_target', 'milestone', 'chart_version', 'fact_snapshot_id'})
PROVIDER_CHART_EVIDENCE_REQUIRED_PARAMS = frozenset({'profile_id', 'begin_ww', 'end_ww', 'run', 'chart_id'})
PROVIDER_CHART_EVIDENCE_OPTIONAL_PARAMS = frozenset({'provider_id', 'bucket', 'series', 'fact_snapshot_id', 'chart_version', 'owner', 'status', 'severity', 'component', 'text'})
PROVIDER_PROFILE_READINESS_REQUIRED_PARAMS = frozenset({'profile_id'})
PROVIDER_PROFILE_READINESS_OPTIONAL_PARAMS = frozenset({'provider_id'})


class ProviderChartDataApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, PROVIDER_CHART_DATA_REQUIRED_PARAMS, PROVIDER_CHART_DATA_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            payload = self.bug_trend_facade.get_provider_chart_payload(
                provider_id=request.GET.get('provider_id'),
                profile_id=request.GET.get('profile_id'),
                begin_ww=request.GET.get('begin_ww'),
                end_ww=request.GET.get('end_ww'),
                chart_id=request.GET.get('chart_id'),
                chart_version=self._chart_version(),
                fact_snapshot_id=request.GET.get('fact_snapshot_id', ''),
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
            )
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        return JsonResponse(payload)


class ProviderChartEvidenceApiView(GracefulTemplateView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, PROVIDER_CHART_EVIDENCE_REQUIRED_PARAMS, PROVIDER_CHART_EVIDENCE_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            payload = self.bug_trend_facade.get_provider_chart_evidence_payload(
                provider_id=request.GET.get('provider_id'),
                profile_id=request.GET.get('profile_id'),
                begin_ww=request.GET.get('begin_ww'),
                end_ww=request.GET.get('end_ww'),
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
