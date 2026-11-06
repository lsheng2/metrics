import json
from dataclasses import asdict, is_dataclass

from django.http import JsonResponse
from django.views import View

from project_management.app.api.report_factories import build_report_assist_service
from project_management.app.api import ProjectError
from project_management.app.api.capture_archive import ArchiveError
from project_management.app.api.reports import ReportError
from project_management.app.api.summary_analysis import AnalysisError
from ui_web.project_access import ProjectAccessError, private_no_store
from ui_web.report_authoring_forms import reject_duplicate_json_keys
from ui_web.views.project_management_views import ProjectAccessMixin


class ReportAssistView(ProjectAccessMixin, View):
    service_factory = staticmethod(build_report_assist_service)
    action = 'root'

    def get(self, request, project_id, stage_id, draft_id, assist_id=None):
        if request.GET:
            return failure(ReportError('REPORT_INVALID'))
        try:
            args = (self.actor(request), str(project_id), str(stage_id), str(draft_id))
            service = self.service_factory()
            if self.action == 'root':
                result = service.describe(*args)
            elif self.action == 'candidate':
                result = service.candidate(*args, str(assist_id))
            elif self.action == 'observe':
                result = service.observe(*args, str(assist_id))
            else:
                return JsonResponse({}, status=405)
            return response(result)
        except (ReportError, ProjectError, ProjectAccessError, ArchiveError, AnalysisError) as error:
            return failure(error)

    def post(self, request, project_id, stage_id, draft_id, assist_id=None):
        try:
            actor = self.actor(request)
            keys = {'command_id'} if self.action == 'cancel' else {
                'command_id', 'expected_revision', 'expected_revision_hash', 'target_ids', 'instruction',
            }
            value = payload(request, keys)
            args = (actor, str(project_id), str(stage_id), str(draft_id))
            service = self.service_factory()
            if self.action == 'cancel':
                result = service.cancel(*args, str(assist_id), command_id=value['command_id'])
            elif self.action == 'root':
                if (type(value['expected_revision']) is not int or value['expected_revision'] < 1
                        or type(value['expected_revision_hash']) is not str or type(value['target_ids']) is not list
                        or any(type(item) is not str for item in value['target_ids'])):
                    raise ReportError('REPORT_INVALID')
                result = service.submit(*args, **value)
            else:
                return JsonResponse({}, status=405)
            return response(result, status=202 if result.state in {'observing', 'unknown', 'prepared'} else 200)
        except (ReportError, ProjectError, ProjectAccessError, ArchiveError, AnalysisError) as error:
            return failure(error)


def payload(request, keys):
    if request.content_type != 'application/json' or len(request.body) > 16384:
        raise ReportError('REPORT_INVALID')
    try:
        value = json.loads(request.body, object_pairs_hook=reject_duplicate_json_keys)
        if not isinstance(value, dict) or set(value) != keys or type(value['command_id']) is not str:
            raise ValueError
        return value
    except (ValueError, UnicodeError):
        raise ReportError('REPORT_INVALID') from None


def json_value(value):
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def response(result, status=200):
    return private_no_store(JsonResponse({'schema_version': 1, 'result': json_value(result), 'error': None}, status=status))


def failure(error):
    code = getattr(error, 'code', 'REPORT_AI_UNAVAILABLE')
    status = 422
    if isinstance(error, ProjectAccessError):
        code, status = 'AUTH_REQUIRED', 401
    elif isinstance(error, ProjectError) or code == 'REPORT_NOT_FOUND':
        code, status = 'REPORT_NOT_FOUND', 404
    elif code in {'REPORT_AI_UNAVAILABLE', 'REPORT_STORAGE_UNAVAILABLE'} or isinstance(error, ArchiveError):
        code, status = 'REPORT_AI_UNAVAILABLE', 503
    elif code in {'REPORT_REVISION_CONFLICT', 'REPORT_AI_BUSY', 'REPORT_AI_CANCELED', 'REPORT_FINALIZED', 'REPORT_FINALIZING'}:
        status = 409
    return private_no_store(JsonResponse({
        'schema_version': 1, 'result': None, 'error': {'code': code, 'message': str(error)},
    }, status=status))
