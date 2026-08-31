import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from bug_metrics.app.api import (
    DashboardCompositionIntent,
    GcxPublicationCallbackRequest,
    GcxPublicationPreconditionRequest,
    ProviderAiDashboardContextQuery,
)

from ..container import ui_web_container
from .bug_trend_view import validate_query_contract


AI_DASHBOARD_CATALOG_REQUIRED_PARAMS = frozenset()
AI_DASHBOARD_CATALOG_OPTIONAL_PARAMS = frozenset({'profile_id'})
AI_DASHBOARD_CONTEXT_REQUIRED_BASE_PARAMS = frozenset({'profile_id'})
AI_DASHBOARD_CONTEXT_OPTIONAL_PARAMS = frozenset({'provider_id', 'chart_id', 'chart_ids', 'chart_version', 'range_mode', 'begin_ww', 'end_ww', 'begin_date', 'end_date'})
SENSITIVE_AI_CONTEXT_KEYS = frozenset({
    'native_query_text',
    'criteria_snapshot',
    'exclusion_snapshot',
    'permission_assumptions',
    'observed_result_contract',
    'password',
    'token',
    'api_key',
    'secret',
    'private_path',
})


class AiDashboardCatalogApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, AI_DASHBOARD_CATALOG_REQUIRED_PARAMS, AI_DASHBOARD_CATALOG_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        return JsonResponse(self.bug_trend_facade.get_ai_dashboard_catalog_payload(request.GET.get('profile_id', '')))


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardIntentValidationApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            intent = DashboardCompositionIntent(
                profile_id=payload['profile_id'],
                dashboard_uid=payload['dashboard_uid'],
                chart_id=payload['chart_id'],
                requested_series=list(payload.get('requested_series', [])),
                range_mode=payload['range_mode'],
                range_start=payload['range_start'],
                range_end=payload['range_end'],
                output_type=payload['output_type'],
                actor=payload.get('actor', 'local_operator'),
                panel_title=payload.get('panel_title', ''),
                visualization=payload.get('visualization', 'timeseries'),
            )
            return JsonResponse(self.bug_trend_facade.validate_ai_dashboard_composition_intent(intent))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardRenderConfigValidationApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            return JsonResponse(
                self.bug_trend_facade.validate_ai_dashboard_render_config_draft(payload['draft_render_config'])
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardGcxPreconditionApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            precondition_request = GcxPublicationPreconditionRequest(
                operation=payload['operation'],
                actor=payload.get('actor', 'local_operator'),
                draft_render_config=payload['draft_render_config'],
                approval_policy=payload.get('approval_policy', 'approval_required'),
            )
            return JsonResponse(self.bug_trend_facade.validate_ai_gcx_publication_precondition(precondition_request))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardGcxPublicationCallbackApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            callback_request = GcxPublicationCallbackRequest(
                operation=payload['operation'],
                actor=payload.get('actor', 'local_operator'),
                dashboard_uid=payload['dashboard_uid'],
                artifact_ref=payload.get('artifact_ref', ''),
                mutation_status=payload['mutation_status'],
                correlation_id=payload['correlation_id'],
                dry_run_proof_id=payload.get('dry_run_proof_id', ''),
            )
            return JsonResponse(self.bug_trend_facade.record_ai_gcx_publication_callback(callback_request))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


class AiDashboardContextApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, ai_dashboard_context_required_params(request), AI_DASHBOARD_CONTEXT_OPTIONAL_PARAMS)
        if invalid_response:
            return invalid_response
        try:
            query = ProviderAiDashboardContextQuery(
                provider_id=request.GET.get('provider_id', ''),
                profile_id=request.GET.get('profile_id', ''),
                begin_ww=request.GET.get('begin_ww', ''),
                end_ww=request.GET.get('end_ww', ''),
                chart_ids=chart_ids_from_query(request),
                chart_version=chart_version_from_query(request),
            )
            return JsonResponse(safe_ai_payload(self.bug_trend_facade.get_ai_dashboard_context_payload(query)))
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)


def json_body(request) -> dict:
    if not request.body:
        return {}
    payload = json.loads(request.body.decode('utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('JSON request body must be an object.')
    return payload


def ai_dashboard_context_required_params(request):
    if request.GET.get('range_mode', 'ww').strip().lower() == 'date':
        return AI_DASHBOARD_CONTEXT_REQUIRED_BASE_PARAMS | frozenset({'begin_date', 'end_date'})
    return AI_DASHBOARD_CONTEXT_REQUIRED_BASE_PARAMS | frozenset({'begin_ww', 'end_ww'})


def chart_ids_from_query(request) -> list[str]:
    chart_ids = []
    raw_values = request.GET.getlist('chart_id') + request.GET.getlist('chart_ids')
    for raw_value in raw_values:
        for chart_id in raw_value.split(','):
            normalized = chart_id.strip()
            if normalized and normalized not in chart_ids:
                chart_ids.append(normalized)
    return chart_ids


def chart_version_from_query(request) -> int:
    raw_value = request.GET.get('chart_version') or '1'
    try:
        return int(raw_value)
    except ValueError:
        raise ValueError('chart_version must be an integer.')


def safe_ai_payload(value):
    if isinstance(value, dict):
        return {
            key: safe_ai_payload(item)
            for key, item in value.items()
            if not is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [safe_ai_payload(item) for item in value]
    return value


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in SENSITIVE_AI_CONTEXT_KEYS or any(fragment in normalized for fragment in ('password', 'token', 'api_key', 'secret', 'private_path'))
