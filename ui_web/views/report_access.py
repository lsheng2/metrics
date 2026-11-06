from django.urls import reverse
from django.utils.translation import gettext as _

from project_management.app.api import reports as report_api
from ui_web.facades.project_reports import default_report_facade
from ui_web.report_authoring_responses import report_status
from ui_web.views.project_management_views import ProjectAccessMixin
from ui_web.views.project_run_views import ProjectRunSubmitView


class ReportAccessMixin(ProjectAccessMixin):
    facade_factory = staticmethod(default_report_facade)

    def error_response(self, request, error):
        if isinstance(error, report_api.ReportError):
            return self.ui_error_response(request, report_error_ui_message(error), report_status(error))
        return super().error_response(request, error)

    def report_context(self, request, actor, project_id, stage_id, **kwargs):
        facade, run_facade = self.facade_factory(), ProjectRunSubmitView.facade_factory()
        context = facade.stage_context(actor, str(project_id), str(stage_id),
                                       include_operations=run_facade.shares_archive(facade.archive), **kwargs)
        context['run'] = run_facade.stage_context(
            actor, str(project_id), str(stage_id), operations_read=context.pop('report_operations', None),
        )
        context['project_language_return_url'] = reverse('ui_web:project_stage_reports', kwargs={
            'project_id': project_id, 'stage_id': stage_id,
        })
        return context

    def draft_context(self, request, actor, project_id, stage_id, draft_id, **kwargs):
        context = self.facade_factory().draft_context(actor, str(project_id), str(stage_id), str(draft_id), **kwargs)
        ids = {'project_id': project_id, 'stage_id': stage_id, 'draft_id': draft_id}
        revision = context['draft'].revision
        context['project_language_return_url'] = reverse('ui_web:report_draft_edit', kwargs=ids)
        context['render_url'] = reverse('ui_web:report_draft_render', kwargs=ids) + f'?revision={revision}'
        context['download_url'] = reverse('ui_web:report_draft_download', kwargs=ids) + f'?revision={revision}&format=html'
        context['clipboard_url'] = reverse('ui_web:report_draft_clipboard', kwargs=ids) + f'?revision={revision}'
        context['completion_url'] = reverse('ui_web:report_draft_completion', kwargs=ids)
        return context


def report_error_ui_message(error):
    return {
        'REPORT_INVALID': _('Report request is invalid.'),
        'REPORT_NOT_FOUND': _('Report is not available.'),
        'REPORT_REVISION_CONFLICT': _('Report revision has changed. Save or reload before continuing.'),
        'REPORT_SOURCE_CHANGED': _('Report source material has changed. Create a new draft.'),
        'REPORT_TEMPLATE_UNSUPPORTED': _('Report template is not supported.'),
        'REPORT_EDIT_TARGET_INVALID': _('Report edit target is not valid.'),
        'REPORT_FINALIZING': _('Report finalization is still pending.'),
        'REPORT_FINALIZED': _('Report is already finalized.'),
        'REPORT_LIMIT': _('Report is over the configured limit.'),
        'REPORT_ARTIFACT_INVALID': _('Report artifact is invalid.'),
        'REPORT_REQUIRED_SLOT_EMPTY': _('Fill all required template slots before finalizing.'),
    }.get(error.code, _('Report request failed.'))
