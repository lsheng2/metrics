from datetime import date
from urllib.parse import urlencode

from django.urls import reverse
from django.utils.translation import gettext as _

from project_management.app.api import reports as report_api
from ui_web.report_forms import new_command_id
from ui_web.report_meeting_forms import MeetingChangeForm, MeetingQueryForm


class ProjectReportMeetingsFacadeMixin:
    def meeting_context(self, actor, project_id, stage_id, *, data=None, change_form=None):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        series = self._series_page(actor, project_id, stage_id)
        choices = tuple((item.series_id, item.name) for item in series.items)
        selected = {key: data.get(key) for key in MeetingQueryForm.base_fields} if data else None
        query = MeetingQueryForm(
            selected, series_choices=choices, auto_id='meeting_query_%s',
            initial={'from_date': date.today().isoformat(), 'through_date': date.today().isoformat()},
        )
        calendar = None
        problem = None
        if selected and query.is_valid():
            try:
                calendar = self.meeting_service().read(actor, project_id, stage_id, **query.interval())
            except report_api.ReportError as error:
                problem = error
        form = change_form
        if form is None and calendar is not None:
            form = MeetingChangeForm(auto_id='meeting_change_%s', initial={
                **query.interval(), 'command_id': new_command_id(),
                'expected_revision': calendar.revision, 'expected_revision_hash': calendar.revision_hash,
                'expected_series_policy_hash': calendar.series_policy_hash,
            })
        labels = {'unrecorded': _('Unrecorded'), 'skipped': _('Skipped'), 'occupied': _('Existing report work')}
        refresh = reverse('ui_web:report_meetings', kwargs={'project_id': project_id, 'stage_id': stage_id})
        if calendar is not None:
            refresh += '?' + urlencode(query.interval())
        return {
            'detail': detail, 'stage': stage, 'meeting_query_form': query,
            'meeting_problem': problem,
            'meeting_change_form': form, 'meeting_calendar': calendar,
            'meeting_rows': () if calendar is None else tuple({
                'local_date': day.local_date, 'state': day.state, 'label': labels[day.state],
                'reason': day.reason, 'recorded_by': day.recorded_by, 'work_id': day.work_id,
            } for day in calendar.days),
            'meeting_refresh_url': refresh, 'project_language_return_url': refresh,
        }

    def meeting_service(self):
        if self.continuity_service is None:
            raise report_api.ReportError('REPORT_CALENDAR_UNAVAILABLE')
        return report_api.ReportMeetingService(self.continuity_service)

    def change_meetings(self, actor, project_id, stage_id, form):
        values = form.cleaned_data
        return self.meeting_service().change(
            actor, project_id, stage_id, **form.interval(),
            command_id=str(values['command_id']), expected_revision=values['expected_revision'],
            expected_revision_hash=values['expected_revision_hash'],
            expected_series_policy_hash=values['expected_series_policy_hash'],
            action=values['action'], reason=values['reason'],
        )
