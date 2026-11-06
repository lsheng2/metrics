from dataclasses import asdict, is_dataclass

from django.http import JsonResponse
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from project_management.app.api.factories import build_project_api
from project_management.app.api.report_factories import build_report_completion_service
from ui_web.project_access import ProjectAccessError, private_no_store
from ui_web.report_completion_forms import parse_completion_request
from ui_web.views.project_management_views import ProjectAccessMixin


class ReportDraftCompletionView(ProjectAccessMixin, View):
    completion_factory = staticmethod(lambda: build_report_completion_service())
    project_api_factory = staticmethod(build_project_api)

    def post(self, request, project_id, stage_id, draft_id):
        try:
            actor = self.actor(request)
            detail = self.project_api_factory().get_project(actor, str(project_id))
            stage = next((item for item in detail.stages if item.id == str(stage_id)), None)
            if stage is None:
                raise ProjectError('PROJECT_NOT_FOUND')
            completion = self.completion_factory()
            result = completion.suggest(actor, str(project_id), str(stage_id), str(draft_id), parse_completion_request(request))
            response = private_no_store(JsonResponse(json_value(result), status=status_for_completion(result)))
            if result.error and result.error.retry_after_seconds is not None:
                response['Retry-After'] = str(result.error.retry_after_seconds)
            return response
        except ProjectAccessError:
            return completion_error('COMPLETION_AUTH_REQUIRED', 401)
        except ProjectError:
            return completion_error('REPORT_NOT_FOUND', 404)
        except report_api.ReportError as error:
            return completion_error(error.code, status_for_code(error.code))


def status_for_completion(result):
    if result.status == 'ready':
        return 200
    code = result.error.code if result.error else 'REPORT_INVALID'
    return {
        'COMPLETION_RATE_LIMITED': 429,
        'COMPLETION_ITEM_UNAVAILABLE': 404,
        'COMPLETION_PROVIDER_UNQUALIFIED': 503,
        'COMPLETION_AUTH_REQUIRED': 503,
        'COMPLETION_NETWORK_ERROR': 503,
        'COMPLETION_TIMEOUT': 504,
        'COMPLETION_RESPONSE_INVALID': 502,
        'COMPLETION_SCOPE_UNVERIFIED': 409,
        'COMPLETION_SCOPE_UNAVAILABLE': 409,
        'COMPLETION_SOURCE_CHANGED': 409,
        'COMPLETION_PRINCIPAL_CHANGED': 409,
        'COMPLETION_REQUEST_REPLAY': 409,
        'REPORT_REVISION_CONFLICT': 409,
        'REPORT_FINALIZING': 409,
        'REPORT_FINALIZED': 409,
        'REPORT_NOT_FOUND': 404,
    }.get(code, 422)


def status_for_code(code):
    if code == 'COMPLETION_REQUEST_TOO_LARGE':
        return 413
    if code in {'REPORT_NOT_FOUND'}:
        return 404
    if code in {'COMPLETION_AUTH_REQUIRED'}:
        return 401
    if code in {'REPORT_REVISION_CONFLICT', 'COMPLETION_SCOPE_UNAVAILABLE', 'COMPLETION_SCOPE_UNVERIFIED',
                'COMPLETION_SOURCE_CHANGED'}:
        return 409
    return 400


def completion_error(code, status):
    return private_no_store(JsonResponse({
        'status': 'error',
        'error': {'code': code, 'message': code, 'retry_after_seconds': None},
        'options': [],
    }, status=status))


def json_value(value):
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value
