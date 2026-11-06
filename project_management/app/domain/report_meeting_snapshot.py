from datetime import date, datetime, timedelta
from typing import Mapping

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text
from project_management.app.domain.report_meetings import MAX_CHANGES, local_dates


def validate_meeting_snapshot(snapshot, context):
    try:
        expected = {'schema_version', 'series_id', 'revision', 'revision_hash',
                    'calendar', 'from_date', 'through_date', 'days'}
        if not isinstance(snapshot, Mapping) or set(snapshot) != expected:
            raise ValueError
        if (type(snapshot['schema_version']) is not int or snapshot['schema_version'] != 1
                or snapshot['series_id'] != context['series_id']
                or type(snapshot['revision']) is not int or not 1 <= snapshot['revision'] <= MAX_CHANGES):
            raise ValueError
        validate_hash_text(snapshot['revision_hash'])
        allowed = set(local_dates(snapshot['from_date'], snapshot['through_date']))
        calendar = snapshot['calendar']
        period = context['period']
        if (not isinstance(calendar, Mapping) or set(calendar) != {'calendar_id', 'revision', 'timezone'}
                or calendar['calendar_id'] != period['calendar_id']
                or type(calendar['revision']) is not int or calendar['revision'] != period['calendar_revision']
                or type(calendar['timezone']) is not str or not calendar['timezone']):
            raise ValueError
        meeting = context['meeting']
        if meeting is not None and (
                snapshot['through_date'] != meeting['local_date'] or calendar['timezone'] != meeting['timezone']):
            raise ValueError
        dates_with_work = {item['meeting']['local_date'] for item in context['notes']}
        dates_with_work.update(item['meeting']['local_date'] for item in context['current_observations'])
        if meeting is not None:
            dates_with_work.add(meeting['local_date'])
        days = snapshot['days']
        if not isinstance(days, (list, tuple)) or len(days) > len(allowed):
            raise ValueError
        previous = ''
        for day in days:
            if not isinstance(day, Mapping) or set(day) != {'local_date', 'reason', 'recorded_by', 'recorded_at'}:
                raise ValueError
            local = day['local_date']
            if local not in allowed or local <= previous or local in dates_with_work:
                raise ValueError
            if (type(day['reason']) is not str or len(day['reason']) > 240
                    or any(ord(char) < 32 or ord(char) == 127 for char in day['reason'])
                    or type(day['recorded_by']) is not str or not day['recorded_by']):
                raise ValueError
            recorded = datetime.fromisoformat(day['recorded_at'])
            if recorded.tzinfo is None or recorded.utcoffset() is None:
                raise ValueError
            previous = local
        return snapshot
    except (KeyError, ValueError, TypeError, ReportError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def skipped_dates(context):
    if not context:
        return set()
    return {day['local_date'] for day in context.get('meeting_skips', {}).get('days', ())}


def meeting_skip_text(context):
    if not context:
        return ''
    days = context.get('meeting_skips', {}).get('days', ())
    groups = []
    for day in days:
        local, reason = day['local_date'], day['reason']
        if (groups and groups[-1][2] == reason
                and date.fromisoformat(groups[-1][1]) + timedelta(days=1) == date.fromisoformat(local)):
            groups[-1] = (groups[-1][0], local, reason)
        else:
            groups.append((local, local, reason))
    if not groups:
        return ''
    labels = []
    for first, last, reason in groups:
        label = first if first == last else f'{first} to {last}'
        labels.append(label + (f' ({reason})' if reason else ''))
    return 'Standups skipped: ' + '; '.join(labels) + '.'
