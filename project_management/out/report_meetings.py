from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_meetings import MAX_CHANGES, calendar_hash, verify_change
from project_management.models_report_series import ReportMeetingChange


def read_meeting_history(series, identity):
    rows = tuple(ReportMeetingChange.objects.filter(series=series).order_by('revision')[:MAX_CHANGES + 1])
    if len(rows) > MAX_CHANGES:
        raise ReportError('REPORT_LIMIT')
    previous = calendar_hash({'schema_version': 1, 'identity': identity})
    records = []
    commands = set()
    for revision, row in enumerate(rows, 1):
        payload = verify_change(row.payload_json, identity, revision, previous)
        if (row.revision != revision or row.payload_hash != calendar_hash(payload)
                or str(row.command) != payload['command_id'] or row.request_hash != payload['request_hash']
                or payload['command_id'] in commands):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        commands.add(payload['command_id'])
        records.append(payload)
        previous = row.payload_hash
    return tuple(records), len(records), previous
