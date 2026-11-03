from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api.project_runs import RunError
from ui_web.facades.project_runs import default_project_run_facade
from ui_web.project_access import ProjectAccessError
from ui_web.project_run_forms import ProjectRunRevisionForm, ProjectRunSubmitForm
from ui_web.views.project_management_views import ProjectAccessMixin


STRICT_POST_EXEMPT = {'csrfmiddlewaretoken'}


class ProjectRunAccessMixin(ProjectAccessMixin):
    facade_factory = staticmethod(default_project_run_facade)

    def error_response(self, request, error):
        if isinstance(error, RunError):
            return self.ui_error_response(request, run_error_ui_message(error), run_status(error))
        return super().error_response(request, error)


class ProjectRunSubmitView(ProjectRunAccessMixin, View):
    def post(self, request, project_id, stage_id):
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            reject_unexpected_keys(request.POST, set(ProjectRunSubmitForm.base_fields))
            _, stage = facade._project_stage(actor, str(project_id), str(stage_id))
            form = facade.submit_form(stage, request.POST)
            if not form.is_valid():
                raise RunError('RUN_INVALID')
            operation = facade.submit(actor, str(project_id), str(stage_id), form)
            return redirect('ui_web:project_run_status', project_id=project_id, stage_id=stage_id,
                            operation_id=operation.operation_id)
        except (ProjectAccessError, ProjectError, RunError) as error:
            return self.error_response(request, error)


class ProjectRunStatusView(ProjectRunAccessMixin, View):
    def get(self, request, project_id, stage_id, operation_id):
        try:
            actor = self.actor(request)
            context = self.facade_factory().status_context(
                actor,
                str(project_id),
                str(stage_id),
                str(operation_id),
            )
            if request.headers.get('HX-Request') == 'true':
                return self.render_private(request, 'projects/reports/run_status_fragment.html', context)
            return self.render_private(request, 'projects/reports/run.html', context)
        except (ProjectAccessError, ProjectError, RunError) as error:
            return self.error_response(request, error)


class ProjectRunCancelView(ProjectRunAccessMixin, View):
    def post(self, request, project_id, stage_id, operation_id):
        return self._mutate(request, project_id, stage_id, operation_id, 'cancel')

    def _mutate(self, request, project_id, stage_id, operation_id, action):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(ProjectRunRevisionForm.base_fields))
            form = ProjectRunRevisionForm(request.POST)
            if not form.is_valid():
                raise RunError('RUN_INVALID')
            facade = self.facade_factory()
            if action == 'cancel':
                operation = facade.cancel(actor, str(project_id), str(stage_id), str(operation_id), form)
            else:
                operation = facade.resume(actor, str(project_id), str(stage_id), str(operation_id), form)
            return redirect('ui_web:project_run_status', project_id=project_id, stage_id=stage_id,
                            operation_id=operation.operation_id)
        except (ProjectAccessError, ProjectError, RunError) as error:
            return self.error_response(request, error)


class ProjectRunResumeView(ProjectRunCancelView):
    def post(self, request, project_id, stage_id, operation_id):
        return self._mutate(request, project_id, stage_id, operation_id, 'resume')


def reject_unexpected_keys(data, expected):
    allowed = set(expected) | STRICT_POST_EXEMPT
    if set(data.keys()) - allowed:
        raise RunError('RUN_INVALID')
    for key, values in data.lists():
        if key in expected and len(values) != 1:
            raise RunError('RUN_INVALID')


def run_status(error):
    if error.code == 'RUN_NOT_FOUND':
        return 404
    if error.code in {'RUN_BUSY', 'RUN_COMMAND_CONFLICT', 'RUN_REVISION_CONFLICT', 'RUN_SOURCE_CHANGED'}:
        return 409
    if error.code == 'RUN_LIMIT':
        return 413
    if error.code in {'RUN_UNAVAILABLE', 'RUN_STORAGE_UNAVAILABLE'}:
        return 503
    return 400


def run_error_ui_message(error):
    return {
        'RUN_INVALID': _('Run request is invalid.'),
        'RUN_NOT_FOUND': _('Run operation was not found.'),
        'RUN_UNAVAILABLE': _('Run runtime is not available.'),
        'RUN_BUSY': _('Run operation is busy.'),
        'RUN_COMMAND_CONFLICT': _('Run command conflicts with the stored request.'),
        'RUN_REVISION_CONFLICT': _('Run operation revision has changed.'),
        'RUN_SOURCE_CHANGED': _('Run source changed. Refresh the stage before running.'),
        'RUN_LIMIT': _('Run limit has been reached.'),
        'RUN_DEADLINE_EXPIRED': _('Run deadline has expired.'),
        'RUN_INTERRUPTED': _('Run operation was interrupted.'),
        'RUN_CAPTURE_UNCERTAIN': _('Run capture outcome is uncertain.'),
        'RUN_STORAGE_INVALID': _('Run storage is invalid.'),
        'RUN_STORAGE_UNAVAILABLE': _('Run storage is unavailable.'),
    }.get(error.code, _('Run request failed.'))
