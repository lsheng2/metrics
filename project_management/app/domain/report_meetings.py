from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Mapping

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text


MAX_CHANGE_DAYS = 62
MAX_WINDOW_DAYS = 366
MAX_CHANGES = 1000


@dataclass(frozen=True, slots=True)
class MeetingDay:
    local_date: str
    state: Literal['unrecorded', 'skipped', 'occupied']
    reason: str = ''
    recorded_by: str | None = None
    recorded_at: str | None = None
    work_id: str | None = None


@dataclass(frozen=True, slots=True)
class MeetingCalendarView:
    series_id: str
    series_policy_hash: str
    revision: int
    revision_hash: str
    from_date: str
    through_date: str
    calendar: Mapping
    days: tuple[MeetingDay, ...]


@dataclass(frozen=True, slots=True)
class MeetingChangeResult:
    revision: int
    revision_hash: str
    replayed: bool


def calendar_hash(value):
    return sha256_bytes(canonical_bytes(value))


def local_dates(from_date, through_date, *, limit=MAX_WINDOW_DAYS):
    try:
        if type(from_date) is not str or type(through_date) is not str:
            raise ValueError
        first, last = date.fromisoformat(from_date), date.fromisoformat(through_date)
        if first.isoformat() != from_date or last.isoformat() != through_date or first > last:
            raise ValueError
    except (ValueError, TypeError):
        raise ReportError('REPORT_INVALID') from None
    count = (last - first).days + 1
    if count > limit:
        raise ReportError('REPORT_LIMIT')
    return tuple((first + timedelta(days=index)).isoformat() for index in range(count))


def meeting_request(*, expected_revision, expected_revision_hash, expected_series_policy_hash,
                    action, from_date, through_date, reason):
    if type(expected_revision) is not int or not 0 <= expected_revision < MAX_CHANGES:
        raise ReportError('REPORT_INVALID')
    if type(action) is not str or action not in {'skip', 'restore'} or type(reason) is not str:
        raise ReportError('REPORT_INVALID')
    if len(reason) > 240 or any(ord(char) < 32 or ord(char) == 127 for char in reason):
        raise ReportError('REPORT_INVALID')
    local_dates(from_date, through_date, limit=MAX_CHANGE_DAYS)
    return {
        'expected_revision': expected_revision,
        'expected_revision_hash': validate_hash_text(expected_revision_hash),
        'expected_series_policy_hash': validate_hash_text(expected_series_policy_hash),
        'action': action,
        'from_date': from_date,
        'through_date': through_date,
        'reason': reason.strip(),
    }


def verify_change(payload, identity, revision, previous_hash):
    expected = {
        'schema_version', 'identity', 'revision', 'previous_hash', 'command_id',
        'request_hash', 'request', 'calendar', 'recorded_at',
    }
    try:
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError
        if (type(payload['schema_version']) is not int or payload['schema_version'] != 1
                or payload['identity'] != identity or type(payload['revision']) is not int
                or payload['revision'] != revision or payload['previous_hash'] != previous_hash):
            raise ValueError
        request = meeting_request(**payload['request'])
        if (request != payload['request'] or request['expected_revision'] != revision - 1
                or request['expected_revision_hash'] != previous_hash
                or calendar_hash(request) != payload['request_hash']):
            raise ValueError
        validate_uuid_text(payload['command_id'])
        calendar = payload['calendar']
        if (not isinstance(calendar, dict) or set(calendar) != {'calendar_id', 'revision', 'timezone'}
                or type(calendar['revision']) is not int or calendar['revision'] < 1
                or not all(type(calendar[key]) is str and calendar[key] for key in ('calendar_id', 'timezone'))):
            raise ValueError
        recorded = datetime.fromisoformat(payload['recorded_at'])
        if recorded.tzinfo is None or recorded.utcoffset() is None:
            raise ValueError
        return payload
    except (KeyError, TypeError, ValueError, ReportError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def effective_days(records, from_date, through_date):
    dates = local_dates(from_date, through_date)
    days = {day: MeetingDay(day, 'unrecorded') for day in dates}
    for record in records:
        request = record['request']
        for day in local_dates(request['from_date'], request['through_date'], limit=MAX_CHANGE_DAYS):
            if day not in days:
                continue
            days[day] = MeetingDay(day, 'unrecorded') if request['action'] == 'restore' else MeetingDay(
                day, 'skipped', request['reason'], record['identity']['owner_subject'], record['recorded_at'],
            )
    return tuple(days[day] for day in dates)
