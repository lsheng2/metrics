import json
from uuid import uuid4

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from bug_metrics.app.api import DashboardAiPublishApprovalRequest, DashboardAiPublishRequest

from ..container import ui_web_container
from .ai_dashboard_view import json_body, requested_series_from_payload, safe_ai_payload


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
                artifact_ref=payload.get('artifact_ref', ''),
                artifact_version=int(payload.get('artifact_version', 0) or 0),
                artifact_hash=payload.get('artifact_hash', ''),
                provider_id=payload.get('provider_id', ''),
                workspace_key=payload.get('workspace_key', ''),
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
                artifact_ref=payload.get('artifact_ref', ''),
                artifact_version=int(payload.get('artifact_version', 0) or 0),
                artifact_hash=payload.get('artifact_hash', ''),
                provider_id=payload.get('provider_id', ''),
                workspace_key=payload.get('workspace_key', ''),
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
