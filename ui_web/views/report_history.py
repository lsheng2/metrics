from urllib.parse import unquote

from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from ui_web.project_access import ProjectAccessError
from ui_web.report_forms import ReportLinkedRevisionCreateForm
from ui_web.report_series_forms import ReportSeriesCreateForm, ReportSeriesPolicyForm, ReportWeeklyDraftCreateForm
from ui_web.views.project_management_views import ProjectAccessMixin
from ui_web.views.project_reports import reject_unexpected_keys


STRICT_POST_EXEMPT = {'csrfmiddlewaretoken'}


class ReportHistoryAccessMixin(ProjectAccessMixin):
    from ui_web.facades.project_reports import default_report_facade
    facade_factory = staticmethod(default_report_facade)

    def error_response(self, request, error):
        if isinstance(error, report_api.ReportError):
            from ui_web.views.project_reports import report_error_ui_message, report_status
            return self.ui_error_response(request, report_error_ui_message(error), report_status(error))
        return super().error_response(request, error)

    def report_context(self, request, actor, project_id, stage_id, **kwargs):
        from ui_web.views.project_reports import ProjectRunSubmitView
        from django.urls import reverse
        context = self.facade_factory().stage_context(actor, str(project_id), str(stage_id), **kwargs)
        context['run'] = ProjectRunSubmitView.facade_factory().stage_context(actor, str(project_id), str(stage_id))
        context['project_language_return_url'] = reverse('ui_web:project_stage_reports', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
        })
        return context


class ReportSeriesCreateView(ReportHistoryAccessMixin, View):
    def post(self, request, project_id, stage_id):
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            capture_after = request.POST.get('capture_after') or None
            context = self.report_context(request, actor, project_id, stage_id, capture_after=capture_after)
            reject_unexpected_keys(request.POST, set(ReportSeriesCreateForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = facade.series_create_form(context.get('series_template_choices', ()), request.POST)
            if not form.is_valid():
                context['series_create_form'] = form
                return self.render_private(request, 'projects/reports/stage.html', context, status=400)
            facade.create_series(actor, str(project_id), str(stage_id), form)
            return redirect('ui_web:project_stage_reports', project_id=project_id, stage_id=stage_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportSeriesPolicyView(ReportHistoryAccessMixin, View):
    def post(self, request, project_id, stage_id, series_id):
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            context = self.report_context(request, actor, project_id, stage_id)
            reject_unexpected_keys(request.POST, set(ReportSeriesPolicyForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = ReportSeriesPolicyForm(request.POST, user_template_choices=context.get('series_template_choices', ()))
            if not form.is_valid():
                context['series_rows'] = replace_series_row(context['series_rows'], str(series_id), form=form)
                return self.render_private(request, 'projects/reports/stage.html', context, status=400)
            try:
                facade.save_series_policy(actor, str(project_id), str(stage_id), str(series_id), form)
            except report_api.ReportError as error:
                if error.code == 'REPORT_REVISION_CONFLICT':
                    context['series_rows'] = replace_series_row(
                        context['series_rows'],
                        str(series_id),
                        form=form,
                        error=_('Series policy has changed. Your posted values are still shown.'),
                    )
                    return self.render_private(request, 'projects/reports/stage.html', context, status=409)
                raise
            return redirect('ui_web:project_stage_reports', project_id=project_id, stage_id=stage_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


def replace_series_row(rows, series_id, *, form, error=None):
    return tuple({**row, 'form': form, 'error': error} if row['item'].series_id == series_id else row for row in rows)


class ReportPeriodView(ReportHistoryAccessMixin, View):
    def get(self, request, project_id, stage_id, period_key):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.GET, {'publication_id'}, allow=set(), multi_keys={'publication_id'})
            publication_ids = tuple(request.GET.getlist('publication_id'))
            if not publication_ids:
                raise report_api.ReportError('REPORT_INVALID')
            context = self.facade_factory().period_context(
                actor,
                str(project_id),
                str(stage_id),
                unquote(period_key),
                publication_ids,
            )
            context['project_language_return_url'] = request.get_full_path()
            return self.render_private(request, 'projects/reports/period.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportPublicationLinkedRevisionView(ReportHistoryAccessMixin, View):
    def post(self, request, project_id, stage_id, publication_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.POST, set(ReportLinkedRevisionCreateForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = ReportLinkedRevisionCreateForm(request.POST)
            if not form.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
            draft = self.facade_factory().create_linked_revision(
                actor,
                str(project_id),
                str(stage_id),
                str(publication_id),
                form,
            )
            return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id, draft_id=draft.draft_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)


class ReportWeeklyDraftCreateView(ReportHistoryAccessMixin, View):
    def post(self, request, project_id, stage_id):
        try:
            actor = self.actor(request)
            context = self.report_context(request, actor, project_id, stage_id)
            reject_unexpected_keys(
                request.POST,
                set(ReportWeeklyDraftCreateForm.base_fields),
                allow=STRICT_POST_EXEMPT,
                multi_keys={'publication_id'},
            )
            form = ReportWeeklyDraftCreateForm(
                request.POST,
                template_choices=context.get('weekly_template_choices', ()),
                publication_choices=context['weekly_create_form'].fields['publication_id'].choices,
                series_choices=context['weekly_create_form'].fields['series_id'].choices[1:],
                period_choices=context['weekly_create_form'].fields['period_key'].choices[1:],
            )
            if not form.is_valid():
                context['weekly_create_form'] = form
                return self.render_private(request, 'projects/reports/stage.html', context, status=400)
            draft = self.facade_factory().create_weekly_draft(actor, str(project_id), str(stage_id), form)
            return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id, draft_id=draft.draft_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.error_response(request, error)
