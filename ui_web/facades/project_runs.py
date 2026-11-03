from dataclasses import dataclass

from django.urls import reverse

from project_management.app.api import ProjectError
from project_management.app.api.project_runs import RunError
from project_management.runtime import get_project_runtime, build_run_read_service
from ui_web.project_run_forms import ProjectRunRevisionForm, run_submit_form


def default_project_run_facade():
    runtime = get_project_runtime()
    if runtime is not None:
        return ProjectRunFacade(runtime.run_service.project_api, runtime.run_service, runtime_ready=True)
    try:
        service = build_run_read_service()
        return ProjectRunFacade(service.project_api, service, runtime_ready=False)
    except Exception:
        return ProjectRunFacade(None, None, runtime_ready=False)


@dataclass(frozen=True, slots=True)
class OperationStatusLinks:
    produced_revision_url: str | None
    latest_draft_url: str | None


class ProjectRunFacade:
    def __init__(self, project_api, run_service, *, runtime_ready):
        self.project_api = project_api
        self.run_service = run_service
        self.runtime_ready = runtime_ready

    def stage_context(self, actor, project_id, stage_id):
        if self.project_api is None or self.run_service is None:
            return {
                'runtime_ready': False,
                'run_form': None,
                'operations': (),
                'run_unavailable': True,
            }
        detail, stage = self._project_stage(actor, project_id, stage_id)
        try:
            operations = self.run_service.list(actor, project_id, stage_id, limit=10)
        except RunError:
            operations = ()
        return {
            'runtime_ready': self.runtime_ready,
            'run_form': run_submit_form(stage),
            'operations': operations,
            'run_unavailable': False,
        }

    def submit(self, actor, project_id, stage_id, form):
        return self._service().submit(actor, project_id, stage_id, form.request())

    def status_context(self, actor, project_id, stage_id, operation_id):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        operation = self._service().get(actor, project_id, stage_id, operation_id)
        return {
            'detail': detail,
            'stage': stage,
            'operation': operation,
            'links': self._links(project_id, stage_id, operation),
            'cancel_form': ProjectRunRevisionForm(initial={'expected_revision': operation.revision}),
            'resume_form': ProjectRunRevisionForm(initial={'expected_revision': operation.revision}),
            'runtime_ready': self.runtime_ready,
            'project_language_return_url': reverse('ui_web:project_run_status', kwargs={
                'project_id': project_id,
                'stage_id': stage_id,
                'operation_id': operation_id,
            }),
        }

    def cancel(self, actor, project_id, stage_id, operation_id, form):
        return self._service().cancel(
            actor,
            project_id,
            stage_id,
            operation_id,
            expected_revision=form.cleaned_data['expected_revision'],
        )

    def resume(self, actor, project_id, stage_id, operation_id, form):
        return self._service().resume(
            actor,
            project_id,
            stage_id,
            operation_id,
            expected_revision=form.cleaned_data['expected_revision'],
        )

    def submit_form(self, stage, data=None):
        return run_submit_form(stage, data)

    def revision_form(self, data=None):
        return ProjectRunRevisionForm(data)

    def _links(self, project_id, stage_id, operation):
        if operation.draft_id is None or operation.draft_revision is None:
            return OperationStatusLinks(None, None)
        render = reverse('ui_web:report_draft_render', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': operation.draft_id,
        }) + f'?revision={operation.draft_revision}'
        latest = reverse('ui_web:report_draft_edit', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': operation.draft_id,
        })
        return OperationStatusLinks(render, latest)

    def _project_stage(self, actor, project_id, stage_id):
        if self.project_api is None:
            raise RunError('RUN_UNAVAILABLE')
        detail = self.project_api.get_project(actor, project_id)
        for stage in detail.stages:
            if stage.id == stage_id:
                return detail, stage
        raise ProjectError('PROJECT_NOT_FOUND')

    def _service(self):
        if self.run_service is None:
            raise RunError('RUN_UNAVAILABLE')
        return self.run_service
