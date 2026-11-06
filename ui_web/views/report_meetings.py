from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from project_management.app.api import ProjectError
from project_management.app.api import reports as report_api
from ui_web.project_access import ProjectAccessError
from ui_web.report_authoring_responses import wants_json
from ui_web.report_daily_responses import daily_error_message, daily_json, daily_request_data, daily_status
from ui_web.report_meeting_forms import MeetingChangeForm, MeetingQueryForm
from ui_web.views.project_reports import ReportAccessMixin, reject_unexpected_keys


class ReportMeetingsView(ReportAccessMixin, View):
    def get(self, request, project_id, stage_id):
        context = None
        try:
            actor = self.actor(request)
            reject_unexpected_keys(request.GET, set(MeetingQueryForm.base_fields), allow=set())
            context = self.facade_factory().meeting_context(
                actor, str(project_id), str(stage_id), data=request.GET or None,
            )
            if request.GET and not context['meeting_query_form'].is_valid():
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context)
            if context['meeting_problem'] is not None:
                return self.failure(request, context['meeting_problem'], context)
            if wants_json(request):
                return daily_json(result=context['meeting_calendar'])
            return self.render_private(request, 'projects/reports/meetings.html', context)
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.failure(request, error, context)

    def post(self, request, project_id, stage_id):
        context = None
        try:
            actor = self.actor(request)
            data = daily_request_data(request)
            reject_unexpected_keys(data, set(MeetingChangeForm.base_fields), allow={'csrfmiddlewaretoken'})
            form = MeetingChangeForm(data, auto_id='meeting_change_%s')
            facade = self.facade_factory()
            context = facade.meeting_context(
                actor, str(project_id), str(stage_id), data=data, change_form=form,
            )
            if context['meeting_problem'] is not None:
                return self.failure(request, context['meeting_problem'], context)
            if not form.is_valid():
                return self.failure(request, report_api.ReportError('REPORT_INVALID'), context)
            result = facade.change_meetings(actor, str(project_id), str(stage_id), form)
            if wants_json(request):
                return daily_json(result=result)
            target = reverse('ui_web:report_meetings', kwargs={'project_id': project_id, 'stage_id': stage_id})
            return redirect(target + '?' + urlencode(form.interval()))
        except (ProjectAccessError, ProjectError, report_api.ReportError) as error:
            return self.failure(request, error, context)

    def failure(self, request, error, context=None):
        if isinstance(error, (ProjectAccessError, ProjectError)):
            return self.error_response(request, error)
        status = 422 if error.code == 'REPORT_INVALID' else daily_status(error)
        if wants_json(request):
            return daily_json(error=error, status=status)
        if context is None:
            return self.ui_error_response(request, daily_error_message(error), status)
        context['meeting_error'] = daily_error_message(error)
        context['meeting_error_code'] = error.code
        return self.render_private(request, 'projects/reports/meetings.html', context, status=status)
