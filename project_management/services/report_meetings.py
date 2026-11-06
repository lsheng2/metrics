from dataclasses import replace

from django.db import transaction

from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_uuid_text
from project_management.app.domain.report_meetings import (
    MAX_CHANGES, MeetingCalendarView, MeetingChangeResult, calendar_hash,
    effective_days, local_dates, meeting_request, verify_change,
)
from project_management.models_report_series import ReportMeetingChange
from project_management.out.orm_repository import storage_errors
from project_management.out.report_meetings import read_meeting_history
from project_management.services.report_meeting_occupancy import occupied_meetings


class ReportMeetingService:
    def __init__(self, continuity_service):
        self.continuity = continuity_service
        self.archive = continuity_service.archive

    def read(self, actor, project_id, stage_id, *, series_id, from_date, through_date):
        dates = local_dates(from_date, through_date)
        with storage_errors():
            series, policy, identity = self._context(actor, project_id, stage_id, series_id)
            records, revision, revision_hash = read_meeting_history(series, identity)
        days = effective_days(records, from_date, through_date)
        self._require_archive()
        try:
            if self.archive.stage_archive_status(actor, project_id, stage_id) == 'absent':
                occupied = {}
            else:
                with self.archive._report_repository(actor, project_id, stage_id) as repository:
                    occupied = occupied_meetings(repository, self.archive, series_id, dates)
        except ArchiveError as error:
            raise self.continuity._report_error(error) from None
        for day in days:
            if day.state == 'skipped' and day.local_date in occupied:
                raise ReportError('REPORT_ARTIFACT_INVALID')
        return MeetingCalendarView(
            str(series.id), policy.revision_hash, revision, revision_hash, from_date, through_date,
            self._calendar(policy),
            tuple(replace(day, state='occupied', work_id=occupied[day.local_date])
                  if day.local_date in occupied else day for day in days),
        )

    def change(self, actor, project_id, stage_id, *, series_id, command_id,
               expected_revision, expected_revision_hash, expected_series_policy_hash,
               action, from_date, through_date, reason=''):
        command_id = validate_uuid_text(command_id)
        request = meeting_request(
            expected_revision=expected_revision, expected_revision_hash=expected_revision_hash,
            expected_series_policy_hash=expected_series_policy_hash, action=action,
            from_date=from_date, through_date=through_date, reason=reason,
        )
        self._require_archive()
        try:
            with self.archive._meeting_calendar_repository(actor, project_id, stage_id) as repository:
                with storage_errors(), transaction.atomic():
                    series, policy, identity = self._context(actor, project_id, stage_id, series_id)
                    records, revision, previous = read_meeting_history(series, identity)
                    request_hash = calendar_hash(request)
                    for record in records:
                        if record['command_id'] == command_id:
                            if record['request_hash'] != request_hash:
                                raise ReportError('REPORT_MEETING_REVISION_CONFLICT')
                            return MeetingChangeResult(record['revision'], calendar_hash(record), True)
                    self.continuity._lock_active(actor, project_id)
                    series, policy, identity = self._context(actor, project_id, stage_id, series_id)
                    if (revision != expected_revision or previous != expected_revision_hash
                            or policy.revision_hash != expected_series_policy_hash):
                        raise ReportError('REPORT_MEETING_REVISION_CONFLICT')
                    if revision >= MAX_CHANGES:
                        raise ReportError('REPORT_LIMIT')
                    dates = local_dates(from_date, through_date)
                    if action == 'skip' and occupied_meetings(repository, self.archive, series_id, dates):
                        raise ReportError('REPORT_MEETING_OCCUPIED')
                    payload = {
                        'schema_version': 1, 'identity': identity, 'revision': revision + 1,
                        'previous_hash': previous, 'command_id': command_id, 'request_hash': request_hash,
                        'request': request, 'calendar': self._calendar(policy),
                        'recorded_at': self.continuity._now(),
                    }
                    verify_change(payload, identity, revision + 1, previous)
                    digest = calendar_hash(payload)
                    ReportMeetingChange.objects.create(
                        series=series, revision=revision + 1, command=command_id,
                        request_hash=request_hash, payload_json=payload, payload_hash=digest,
                    )
                    return MeetingChangeResult(revision + 1, digest, False)
        except ArchiveError as error:
            if error.code == 'ARCHIVE_BUSY':
                raise ReportError('REPORT_MEETING_REVISION_CONFLICT') from None
            raise self.continuity._report_error(error) from None

    def require_available(self, actor, project_id, stage_id, series_id, meeting_date):
        if self.is_skipped(actor, project_id, stage_id, series_id, meeting_date):
            raise ReportError('REPORT_MEETING_SKIPPED')

    def is_skipped(self, actor, project_id, stage_id, series_id, meeting_date):
        with storage_errors():
            series, _, identity = self._context(actor, project_id, stage_id, series_id)
            records, _, _ = read_meeting_history(series, identity)
        return effective_days(records, meeting_date, meeting_date)[0].state == 'skipped'

    def _context(self, actor, project_id, stage_id, series_id):
        project = self.continuity._owned(actor, project_id)
        stage = self.continuity._stage(project, stage_id)
        series = self.continuity._series(project, stage, series_id)
        policy = self.continuity._policy(series, series.current_revision)
        return series, policy, {
            'project_id': str(project.id), 'stage_id': str(stage.id),
            'series_id': str(series.id), 'owner_subject': actor.subject,
        }

    def _calendar(self, policy):
        calendar = policy.calendar
        return {'calendar_id': calendar.calendar_id, 'revision': calendar.revision, 'timezone': calendar.timezone}

    def _require_archive(self):
        if self.archive is None:
            raise ReportError('REPORT_CALENDAR_UNAVAILABLE')


def require_meeting_available(continuity, actor, project_id, stage_id, series_id, meeting_date):
    ReportMeetingService(continuity).require_available(actor, project_id, stage_id, series_id, meeting_date)
