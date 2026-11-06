from dataclasses import asdict

from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import RunError
from ui_web.project_access import ProjectAccessError
from ui_web.report_authoring_responses import wants_json
from ui_web.report_daily_forms import ReportDailyPreparationForm, ReportDailyPreviewForm, ReportDailyReprepareForm
from ui_web.report_daily_responses import daily_error_message, daily_json, daily_request_data, daily_status
from ui_web.views.project_reports import ReportAccessMixin, reject_unexpected_keys


STRICT_POST_EXEMPT = {'csrfmiddlewaretoken'}


class ReportDailyAccessMixin(ReportAccessMixin):
    def stage_context(self, request, actor, project_id, stage_id, **kwargs):
        return self.report_context(request, actor, project_id, stage_id, **kwargs)

    def daily_context(self, facade, context, data=None, **kwargs):
        return facade.daily_context(context['captures'], context['series_page'],
                                    context['series_template_choices'], data=data, **kwargs)

    def failure(self, request, error, context=None, template='projects/reports/stage.html'):
        if isinstance(error, (ProjectAccessError, ProjectError)):
            return self.error_response(request, error)
        status = daily_status(error)
        if wants_json(request):
            return daily_json(error=error, status=status)
        if context is None:
            return self.ui_error_response(request, daily_error_message(error), status)
        context['daily_error'] = daily_error_message(error)
        context['daily_error_code'] = error.code
        return self.render_private(request, template, context, status=status)

    def result_response(self, request, result, project_id, stage_id):
        if wants_json(request):
            return daily_json(result=result, status=202 if result.operation_id and result.state == 'queued' else 200)
        if result.publication_ref:
            return redirect('ui_web:report_publication', project_id=project_id, stage_id=stage_id,
                            publication_id=result.publication_ref.publication_id)
        if result.operation_id is not None:
            return redirect('ui_web:project_run_status', project_id=project_id, stage_id=stage_id,
                            operation_id=result.operation_id)
        return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id, draft_id=result.draft_id)


class ReportBaselinePreviewView(ReportDailyAccessMixin, View):
    def get(self, request, project_id, stage_id):
        context = None
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.GET, set(ReportDailyPreviewForm.base_fields), allow=set())
            facade = self.facade_factory()
            context = self.stage_context(request, actor, project_id, stage_id,
                                         capture_after=request.GET.get('capture_after') or None)
            form = self.daily_context(facade, context, request.GET)['daily_preview_form']
            if not form.is_valid():
                context['daily_preview_form'] = form
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context)
            preview = facade.preview_daily(actor, str(project_id), str(stage_id), form)
            existing = facade.preparation_service.for_meeting(
                actor, str(project_id), str(stage_id),
                series_id=form.cleaned_data['series_id'], meeting_date=form.meeting_date_value(),
            )
            context.update(self.daily_context(facade, context, request.GET, preview=preview, selection_preview=True))
            context['daily_existing'] = existing
            if wants_json(request):
                return daily_json(result={'preview': asdict(preview),
                                          'existing': None if existing is None else asdict(existing)})
            return self.render_private(request, 'projects/reports/stage.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            return self.failure(request, error, context)


class ReportPreparationCreateView(ReportDailyAccessMixin, View):
    def post(self, request, project_id, stage_id):
        context = None
        form = None
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            data = daily_request_data(request)
            reject_unexpected_keys(
                data,
                set(ReportDailyPreparationForm.base_fields),
                allow=STRICT_POST_EXEMPT,
                multi_keys={'acknowledge_gap_draft_ids'},
            )
            context = self.stage_context(request, actor, project_id, stage_id,
                                         capture_after=data.get('capture_after') or None)
            context.update(self.daily_context(facade, context, data))
            form = context['daily_prepare_form']
            if not form.is_valid():
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context)
            result = facade.prepare_daily(actor, str(project_id), str(stage_id), form)
            if result.selection_conflicts:
                if wants_json(request):
                    return daily_json(result=result, status=409)
                context.update(self.daily_context(facade, context, data, prepare_form=form, result=result))
                return self.render_private(request, 'projects/reports/stage.html', context, status=409)
            return self.result_response(request, result, project_id, stage_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            if (context is not None and form is not None and form.is_valid()
                    and getattr(error, 'code', '') in {'REPORT_BASELINE_PENDING', 'REPORT_BASELINE_CONFLICT'}):
                try:
                    preview = facade.preview_daily(actor, str(project_id), str(stage_id), form)
                    context.update(self.daily_context(facade, context, data, preview=preview, prepare_form=form))
                except report_api.ReportError as preview_error:
                    context['daily_preview_error'] = daily_error_message(preview_error)
            return self.failure(request, error, context)


class ReportPreparationDetailView(ReportDailyAccessMixin, View):
    def get(self, request, project_id, stage_id, preparation_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.GET, set(), allow=set())
            facade = self.facade_factory()
            context = self.stage_context(request, actor, project_id, stage_id)
            context.update(facade.preparation_context(actor, str(project_id), str(stage_id),
                                                      str(preparation_id), context['series_template_choices']))
            if wants_json(request):
                return daily_json(result=context['preparation_details'])
            return self.render_private(request, 'projects/reports/preparation.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            return self.failure(request, error)


class ReportPreparationReprepareView(ReportDailyAccessMixin, View):
    def post(self, request, project_id, stage_id, preparation_id):
        context = None
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            data = daily_request_data(request)
            reject_unexpected_keys(data, set(ReportDailyReprepareForm.base_fields), allow=STRICT_POST_EXEMPT)
            context = self.stage_context(request, actor, project_id, stage_id)
            context.update(facade.preparation_context(actor, str(project_id), str(stage_id), str(preparation_id),
                                                      context['series_template_choices'], data))
            form = context['daily_reprepare_form']
            if not form.is_valid():
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context,
                                    'projects/reports/preparation.html')
            if str(form.cleaned_data['preparation_id']) != str(preparation_id):
                raise report_api.ReportError('REPORT_INVALID')
            result = facade.reprepare_daily(actor, str(project_id), str(stage_id), form)
            if wants_json(request):
                return daily_json(result=result, status=202 if result.operation_id else 200)
            if result.preparation_id == str(preparation_id):
                return redirect('ui_web:report_draft_edit', project_id=project_id, stage_id=stage_id,
                                draft_id=result.draft_id)
            return redirect('ui_web:report_preparation_detail', project_id=project_id, stage_id=stage_id,
                            preparation_id=result.preparation_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            return self.failure(request, error, context, 'projects/reports/preparation.html')
