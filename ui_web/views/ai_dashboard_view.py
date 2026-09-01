import json
from uuid import uuid4

from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from bug_metrics.app.api import (
    DashboardAiPublishApprovalRequest,
    DashboardAiPublishRequest,
    DashboardAiWorkflowRequest,
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


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardPublishDemoApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            publish_request = DashboardAiPublishRequest(
                profile_id=payload['profile_id'],
                dashboard_uid=payload['dashboard_uid'],
                chart_id=payload.get('chart_id', 'open_bug_trend'),
                requested_series=requested_series_from_payload(payload.get('requested_series', ['new_critical_high'])),
                range_mode=payload.get('range_mode', 'ww'),
                range_start=payload.get('range_start', payload.get('begin_ww', '26WW32')),
                range_end=payload.get('range_end', payload.get('end_ww', '26WW35')),
                operation=payload.get('operation', 'grafana_import'),
                actor=payload.get('actor', 'local_operator'),
                approval_id=payload.get('approval_id', ''),
                dry_run_proof_id=payload.get('dry_run_proof_id', ''),
                output_type=payload.get('output_type', 'render_config_draft'),
                panel_title=payload.get('panel_title', ''),
                visualization=payload.get('visualization', 'timeseries'),
            )
            correlation_id = payload.get('correlation_id') or f'metrics-publish-{uuid4()}'
            return JsonResponse(safe_ai_payload(self.bug_trend_facade.publish_ai_grafana_dashboard_demo(publish_request, correlation_id)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardPublishApprovalApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        approval_id = request.GET.get('approval_id', '')
        if not approval_id:
            return JsonResponse({'error': 'approval_id is required.'}, status=400)
        return JsonResponse(safe_ai_payload(self.bug_trend_facade.get_ai_grafana_publish_approval(approval_id)))

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            approval_request = DashboardAiPublishApprovalRequest(
                profile_id=payload['profile_id'],
                dashboard_uid=payload['dashboard_uid'],
                chart_id=payload.get('chart_id', 'open_bug_trend'),
                requested_series=requested_series_from_payload(payload.get('requested_series', ['new_critical_high'])),
                range_mode=payload.get('range_mode', 'ww'),
                range_start=payload.get('range_start', payload.get('begin_ww', '26WW32')),
                range_end=payload.get('range_end', payload.get('end_ww', '26WW35')),
                dry_run_proof_id=payload['dry_run_proof_id'],
                actor=payload.get('actor', 'local_operator'),
            )
            return JsonResponse(safe_ai_payload(self.bug_trend_facade.request_ai_grafana_publish_approval(approval_request)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardPublishApprovalDecisionApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            return JsonResponse(
                safe_ai_payload(
                    self.bug_trend_facade.decide_ai_grafana_publish_approval(
                        payload['approval_id'],
                        payload['decision'],
                        payload.get('actor', 'local_operator'),
                    )
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return JsonResponse({'error': str(error)}, status=400)


class AiDashboardPublishHistoryApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        try:
            limit = int(request.GET.get('limit', '25'))
            return JsonResponse(safe_ai_payload(self.bug_trend_facade.list_ai_grafana_publish_history(limit)))
        except ValueError as error:
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


class AiDashboardWorkspaceContextApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get(self, request, *args, **kwargs):
        invalid_response = validate_query_contract(request, frozenset({'profile_id'}), frozenset())
        if invalid_response:
            return invalid_response
        return JsonResponse(safe_ai_payload(self.bug_trend_facade.get_ai_workspace_context_bundle_payload(request.GET['profile_id'])))


class AiDashboardWorkflowView(TemplateView):
    template_name = 'ai_dashboard_workflow.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form_values = ai_dashboard_workflow_form_values(self.request.GET)
        context.update(self._base_context(form_values))
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        form_values = ai_dashboard_workflow_form_values(request.POST)
        context.update(self._base_context(form_values))
        try:
            context['workflow_result'] = safe_ai_payload(
                self.bug_trend_facade.run_ai_dashboard_workflow(ai_dashboard_workflow_request_from_payload(form_values))
            )
        except (KeyError, TypeError, ValueError) as error:
            context['workflow_error'] = str(error)
        return self.render_to_response(context)

    def _base_context(self, form_values: dict) -> dict:
        catalog = self.bug_trend_facade.get_ai_dashboard_catalog_payload('')
        return {
            'form_values': form_values,
            'catalog': safe_ai_payload(catalog),
            'sidecar_status': safe_ai_payload(self.bug_trend_facade.get_ai_sidecar_status_payload()),
            'workflow_api_url': self.request.build_absolute_uri(reverse('ui_web:ai_dashboard_workflow_api')),
            'profile_options': self._profile_options(catalog),
            'chart_options': self._chart_options(catalog),
            'publish_history': safe_ai_payload(self.bug_trend_facade.list_ai_grafana_publish_history(10)),
        }

    def _profile_options(self, catalog: dict) -> list[dict]:
        return [
            {
                'profile_id': profile.get('profile_id', ''),
                'provider_id': profile.get('provider_id', ''),
                'status': profile.get('status', ''),
            }
            for profile in catalog.get('profiles', [])
        ]

    def _chart_options(self, catalog: dict) -> list[dict]:
        return [
            {
                'chart_id': chart_id,
                'title': recipe.get('title', chart_id),
                'allowed_series': ', '.join(recipe.get('allowed_series', [])),
                'support_status': recipe.get('support_status', ''),
            }
            for chart_id, recipe in sorted(catalog.get('chart_recipes', {}).items())
        ]


@method_decorator(csrf_exempt, name='dispatch')
class AiDashboardWorkflowApiView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def post(self, request, *args, **kwargs):
        try:
            payload = json_body(request)
            return JsonResponse(
                safe_ai_payload(
                    self.bug_trend_facade.run_ai_dashboard_workflow(ai_dashboard_workflow_request_from_payload(payload))
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
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


def ai_dashboard_workflow_form_values(payload) -> dict:
    return {
        'profile_id': str(payload.get('profile_id', 'nvu-ttl-hsdes') or 'nvu-ttl-hsdes'),
        'dashboard_uid': str(payload.get('dashboard_uid', 'ip-quality-dashboard') or 'ip-quality-dashboard'),
        'chart_id': str(payload.get('chart_id', 'open_bug_trend') or 'open_bug_trend'),
        'requested_series': str(payload.get('requested_series', 'new_critical_high') or 'new_critical_high'),
        'range_mode': str(payload.get('range_mode', 'ww') or 'ww'),
        'range_start': str(payload.get('range_start', payload.get('begin_ww', '26WW10')) or '26WW10'),
        'range_end': str(payload.get('range_end', payload.get('end_ww', '26WW35')) or '26WW35'),
        'operation': str(payload.get('operation', 'grafana_import') or 'grafana_import'),
        'actor': str(payload.get('actor', 'local_operator') or 'local_operator'),
        'panel_title': str(payload.get('panel_title', '') or ''),
        'visualization': str(payload.get('visualization', 'timeseries') or 'timeseries'),
    }


def ai_dashboard_workflow_request_from_payload(payload: dict) -> DashboardAiWorkflowRequest:
    return DashboardAiWorkflowRequest(
        profile_id=str(payload['profile_id']),
        dashboard_uid=str(payload.get('dashboard_uid', 'ip-quality-dashboard') or 'ip-quality-dashboard'),
        chart_id=str(payload.get('chart_id', 'open_bug_trend') or 'open_bug_trend'),
        requested_series=requested_series_from_payload(payload.get('requested_series', ['new_critical_high'])),
        range_mode=str(payload.get('range_mode', 'ww') or 'ww'),
        range_start=str(payload.get('range_start', payload.get('begin_ww', '26WW10')) or '26WW10'),
        range_end=str(payload.get('range_end', payload.get('end_ww', '26WW35')) or '26WW35'),
        operation=str(payload.get('operation', 'grafana_import') or 'grafana_import'),
        actor=str(payload.get('actor', 'local_operator') or 'local_operator'),
        panel_title=str(payload.get('panel_title', '') or ''),
        visualization=str(payload.get('visualization', 'timeseries') or 'timeseries'),
    )


def requested_series_from_payload(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(',') if item.strip()]


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
