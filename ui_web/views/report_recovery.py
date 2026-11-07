import json

from django.http import JsonResponse
from django.views import View

from project_management.app.api import ProjectError, reports as report_api
from project_management.app.api.capture_archive import ArchiveError
from project_management.app.api.report_factories import build_report_service
from project_management.app.domain.report_recovery import RECOVERY_LIMIT, REQUEST_KEYS
from ui_web.project_access import ProjectAccessError, private_no_store
from ui_web.report_authoring_forms import reject_duplicate_json_keys
from ui_web.report_authoring_responses import report_status
from ui_web.views.project_management_views import ProjectAccessMixin


class ReportRecoveryView(ProjectAccessMixin, View):
    service_factory = staticmethod(lambda: report_api.ReportRecoveryService(build_report_service()))

    def get(self, request, project_id, stage_id, draft_id, client_id=None):
        try:
            if request.GET:
                raise report_api.ReportError('REPORT_INVALID')
            args = self.actor(request), str(project_id), str(stage_id), str(draft_id)
            service = self.service_factory()
            value = service.list(*args) if client_id is None else service.get(*args, str(client_id))
            return response(value)
        except (ProjectAccessError, ProjectError, ArchiveError, report_api.ReportError) as error:
            return failure(error)

    def post(self, request, project_id, stage_id, draft_id, client_id=None):
        try:
            actor = self.actor(request)
            if request.content_type != 'application/json' or len(request.body) > RECOVERY_LIMIT:
                raise report_api.ReportError('REPORT_LIMIT')
            value = json.loads(request.body, object_pairs_hook=reject_duplicate_json_keys)
            expected = REQUEST_KEYS if client_id is None else {'expected_sequence'}
            if not isinstance(value, dict) or set(value) != expected:
                raise report_api.ReportError('REPORT_INVALID')
            service = self.service_factory()
            args = actor, str(project_id), str(stage_id), str(draft_id)
            if client_id is None:
                return response(service.put(*args, **value))
            service.discard(*args, str(client_id), expected_sequence=value['expected_sequence'])
            return response({'discarded': True})
        except (ValueError, UnicodeError):
            return failure(report_api.ReportError('REPORT_INVALID'))
        except (ProjectAccessError, ProjectError, ArchiveError, report_api.ReportError) as error:
            return failure(error)


def response(value):
    return private_no_store(JsonResponse({'result': value, 'error': None}))


def failure(error):
    if isinstance(error, ArchiveError):
        error = report_api.ReportError('REPORT_STORAGE_UNAVAILABLE')
    status = (401 if isinstance(error, ProjectAccessError)
              else 404 if isinstance(error, ProjectError) else report_status(error))
    return private_no_store(JsonResponse({
        'result': None, 'error': {'code': getattr(error, 'code', 'REPORT_INVALID')},
    }, status=status))
