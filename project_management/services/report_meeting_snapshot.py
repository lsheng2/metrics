from dataclasses import asdict
from datetime import date, timedelta

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_meeting_snapshot import validate_meeting_snapshot
from project_management.app.domain.report_meetings import calendar_hash, effective_days, local_dates
from project_management.out.report_meetings import read_meeting_history
from project_management.services.report_meetings import ReportMeetingService


def freeze_meeting_snapshot(continuity, actor, project_id, stage_id, context, baseline):
    service = ReportMeetingService(continuity)
    series, _, identity = service._context(actor, project_id, stage_id, context['series_id'])
    records, revision, digest = read_meeting_history(series, identity)
    prior = None if baseline is None else baseline.get('meeting_skips')
    if prior is not None:
        old_revision = prior['revision']
        if old_revision > revision or calendar_hash(records[old_revision - 1]) != prior['revision_hash']:
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    if not records:
        return context
    through = context['meeting']['local_date']
    if baseline is None:
        from_date = min((record['request']['from_date'] for record in records
                         if record['request']['from_date'] <= through), default=through)
    elif baseline['period'] == context['period'] and prior is not None:
        from_date = prior['from_date']
    else:
        from_date = (date.fromisoformat(baseline['meeting']['local_date']) + timedelta(days=1)).isoformat()
    local_dates(from_date, through)
    days = effective_days(records, from_date, through)
    snapshot = {
        'schema_version': 1, 'series_id': context['series_id'], 'revision': revision,
        'revision_hash': digest, 'calendar': {
            'calendar_id': context['meeting']['calendar_id'],
            'revision': context['meeting']['calendar_revision'],
            'timezone': context['meeting']['timezone'],
        },
        'from_date': from_date, 'through_date': through,
        'days': [
            {key: value for key, value in asdict(day).items() if key not in {'state', 'work_id'}}
            for day in days if day.state == 'skipped'
        ],
    }
    result = {**context, 'schema_version': max(2, context['schema_version']), 'meeting_skips': snapshot}
    validate_meeting_snapshot(snapshot, result)
    return result
