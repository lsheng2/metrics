from dataclasses import asdict

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import RunError
from ui_web.project_access import ProjectAccessError
from ui_web.report_authoring_responses import wants_json
from ui_web.report_daily_forms import (
    ReportDailyPreparationForm, ReportDailyPreviewForm, ReportDailyPreviewRequestForm, ReportDailyReprepareForm,
)
from ui_web.report_daily_responses import daily_error_message, daily_json, daily_request_data, daily_status
from ui_web.views.project_reports import ReportAccessMixin, reject_unexpected_keys


STRICT_POST_EXEMPT = {'csrfmiddlewaretoken'}


class ReportDailyAccessMixin(ReportAccessMixin):
    def control_context(self, facade, actor, project_id, stage_id, *, data=None, load_captures=False, capture_page=None):
        context = facade.control_context(actor, str(project_id), str(stage_id), data=data,
                                         load_captures=load_captures, capture_page=capture_page)
        context['project_language_return_url'] = reverse('ui_web:project_stage_reports', kwargs={
            'project_id': project_id, 'stage_id': stage_id,
        })
        return context

    def bound_context(self, facade, actor, project_id, stage_id, data):
        try:
            context = self.control_context(facade, actor, project_id, stage_id, data=data)
            context.update(self.daily_context(facade, context, data))
            return context
        except (ProjectError, report_api.ReportError):
            return None

    def daily_context(self, facade, context, data=None, **kwargs):
        return facade.daily_context(context['captures'], context['series_page'],
                                    context['series_template_choices'], data=data, **kwargs)

    def failure(self, request, error, context=None, template='projects/reports/preparation_error.html'):
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
        facade = None
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.GET, set(ReportDailyPreviewForm.base_fields), allow=set())
            facade = self.facade_factory()
            form = ReportDailyPreviewRequestForm(request.GET)
            if not form.is_valid():
                if not wants_json(request):
                    context = self.bound_context(facade, actor, project_id, stage_id, request.GET)
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context)
            read = facade.preview_daily_query(actor, str(project_id), str(stage_id), form,
                                              include_captures=not wants_json(request))
            preview, existing = read.preview, read.existing
            if wants_json(request):
                return daily_json(result={'preview': asdict(preview),
                                          'existing': None if existing is None else asdict(existing)})
            context = self.control_context(facade, actor, project_id, stage_id, data=request.GET, capture_page=read.captures)
            context.update(self.daily_context(facade, context, request.GET, preview=preview, selection_preview=True))
            context['daily_existing'] = existing
            return self.render_private(request, 'projects/reports/preparation_error.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            if facade is not None and context is None and not wants_json(request):
                context = self.bound_context(facade, actor, project_id, stage_id, request.GET)
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
            form = ReportDailyPreparationForm(data)
            if not form.is_valid():
                if not wants_json(request):
                    context = self.bound_context(facade, actor, project_id, stage_id, data)
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context)
            result = facade.prepare_daily(actor, str(project_id), str(stage_id), form)
            if result.selection_conflicts:
                if wants_json(request):
                    return daily_json(result=result, status=409)
                context = self.control_context(facade, actor, project_id, stage_id, data=data)
                context.update(self.daily_context(facade, context, data, result=result))
                return self.render_private(request, 'projects/reports/preparation_error.html', context, status=409)
            return self.result_response(request, result, project_id, stage_id)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            if wants_json(request) or form is None:
                return self.failure(request, error)
            context = self.bound_context(facade, actor, project_id, stage_id, data)
            if (context is not None and form is not None and form.is_valid()
                    and getattr(error, 'code', '') in {'REPORT_BASELINE_PENDING', 'REPORT_BASELINE_CONFLICT'}):
                try:
                    preview = facade.preview_daily(actor, str(project_id), str(stage_id), form)
                    context.update(self.daily_context(facade, context, data, preview=preview))
                except report_api.ReportError as preview_error:
                    context['daily_preview_error'] = daily_error_message(preview_error)
            return self.failure(request, error, context)


class ReportPreparationDetailView(ReportDailyAccessMixin, View):
    def get(self, request, project_id, stage_id, preparation_id):
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.GET, set(), allow=set())
            facade = self.facade_factory()
            details = facade.preparation_details(actor, str(project_id), str(stage_id), str(preparation_id))
            if wants_json(request):
                return daily_json(result=details)
            context = self.control_context(facade, actor, project_id, stage_id,
                                           load_captures=facade.can_reprepare(details, str(preparation_id)))
            context.update(facade.preparation_controls(details, str(preparation_id), context['series_template_choices']))
            return self.render_private(request, 'projects/reports/preparation.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError, RunError) as error:
            return self.failure(request, error)


class ReportPreparationReprepareView(ReportDailyAccessMixin, View):
    def post(self, request, project_id, stage_id, preparation_id):
        context = None
        form = None
        try:
            actor = self.actor(request)
            facade = self.facade_factory()
            data = daily_request_data(request)
            reject_unexpected_keys(data, set(ReportDailyReprepareForm.base_fields), allow=STRICT_POST_EXEMPT)
            form = ReportDailyReprepareForm(data)
            if not form.is_valid():
                raise report_api.ReportError('REPORT_INVALID')
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
            if not wants_json(request) and form is not None:
                try:
                    context = self.control_context(facade, actor, project_id, stage_id, data=data)
                    context.update(facade.preparation_context(actor, str(project_id), str(stage_id), str(preparation_id),
                                                              context['series_template_choices'], data))
                except (ProjectError, report_api.ReportError, RunError):
                    context = None
            return self.failure(request, error, context, 'projects/reports/preparation.html')
