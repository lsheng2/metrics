from datetime import datetime
import re
from urllib.parse import quote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from project_management.app.domain.captures import ArchiveError, WorkItemIdentity
from project_management.app.domain.report_contracts import ReportLimits, ReportSelection, ReportSourceError
from project_management.app.domain.report_values import frozen_json
from project_management.storage.paths import validate_uuid


JIRA_KEY = re.compile(r'[A-Z][A-Z0-9_]{1,31}-[1-9][0-9]{0,15}')
PURPOSES = {'standup', 'historical_export'}


def validated_selection(selection):
    if not isinstance(selection, ReportSelection):
        raise ReportSourceError('REPORT_INVALID')
    try:
        validate_uuid(selection.capture_id)
        if selection.baseline_publication_id is not None:
            validate_uuid(selection.baseline_publication_id)
        if selection.parent_publication_id is not None:
            validate_uuid(selection.parent_publication_id)
    except ArchiveError:
        raise ReportSourceError('REPORT_INVALID') from None
    if selection.purpose not in PURPOSES:
        raise ReportSourceError('REPORT_INVALID')
    try:
        timezone = ZoneInfo(selection.timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ReportSourceError('REPORT_INVALID') from None
    return timezone


def checked_limits(limits):
    limits = limits or ReportLimits()
    if not isinstance(limits, ReportLimits):
        raise ReportSourceError('REPORT_INVALID')
    for value in (limits.max_snapshot_bytes, limits.max_members, limits.max_captures):
        if type(value) is not int or value <= 0:
            raise ReportSourceError('REPORT_INVALID')
    return limits


def report_date(source_as_of, timezone):
    try:
        parsed = datetime.fromisoformat(source_as_of.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone).date().isoformat()
    except (AttributeError, ValueError, TypeError):
        raise ReportSourceError('REPORT_SOURCE_CHANGED') from None


def safe_source_url(descriptor, identity: WorkItemIdentity) -> str | None:
    if descriptor.provider_id != 'jira' or identity.provider_id != 'jira':
        return None
    if not JIRA_KEY.fullmatch(identity.display_key):
        return None
    if (not isinstance(descriptor.endpoint, str) or '\\' in descriptor.endpoint
            or any(character.isspace() or ord(character) < 32 for character in descriptor.endpoint)):
        return None
    try:
        parsed = urlsplit(descriptor.endpoint)
    except (AttributeError, ValueError):
        return None
    if (parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        return None
    base = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))
    return f'{base}/browse/{quote(identity.display_key, safe="")}'


def json_copy(value):
    return frozen_json(value)


def tuple_json(values):
    return tuple(json_copy(value) for value in values)
