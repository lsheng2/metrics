from dataclasses import asdict, dataclass
from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_continuity import ReportingCalendar, validate_calendar
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_templates import UserTemplateSelection


@dataclass(frozen=True, slots=True)
class ReportContinuityLimits:
    max_series_per_stage: int = 20
    max_policy_revisions: int = 100
    max_context_bytes: int = 8_388_608


@dataclass(frozen=True, slots=True)
class SeriesPolicyRevision:
    series_id: str
    revision: int
    revision_hash: str
    project_id: str
    stage_id: str
    stage_hash: str
    name: str
    calendar: ReportingCalendar
    default_template_selection: UserTemplateSelection
    created_by: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SeriesPage:
    items: tuple[SeriesPolicyRevision, ...]
    next_offset: int | None


def payload_for_series_policy(series_id, revision, project_id, stage_id, stage_hash, actor_subject, created_at,
                              name, calendar, template_selection):
    return {
        'series_id': validate_uuid_text(str(series_id)),
        'revision': _positive_int(revision, 'REPORT_ARTIFACT_INVALID'),
        'project_id': validate_uuid_text(str(project_id)),
        'stage_id': validate_uuid_text(str(stage_id)),
        'stage_hash': validate_hash_text(stage_hash),
        'name': _name(name),
        'calendar': asdict(validate_calendar(calendar)),
        'default_template_selection': asdict(_template_selection(template_selection)),
        'created_by': _text(actor_subject),
        'created_at': _text(created_at),
    }


def series_policy_from_payload(payload) -> SeriesPolicyRevision:
    expected = {
        'series_id', 'revision', 'project_id', 'stage_id', 'stage_hash', 'name',
        'calendar', 'default_template_selection', 'created_by', 'created_at',
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    calendar = _calendar_from_mapping(payload['calendar'])
    selection = _selection_from_mapping(payload['default_template_selection'])
    clean = payload_for_series_policy(
        payload['series_id'], payload['revision'], payload['project_id'], payload['stage_id'],
        payload['stage_hash'], payload['created_by'], payload['created_at'],
        payload['name'], calendar, selection,
    )
    if canonical_bytes(clean) != canonical_bytes(payload):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return SeriesPolicyRevision(
        clean['series_id'], clean['revision'], sha256_bytes(canonical_bytes(clean)),
        clean['project_id'], clean['stage_id'], clean['stage_hash'], clean['name'],
        calendar, selection, clean['created_by'], clean['created_at'],
    )


def _calendar_from_mapping(value):
    if not isinstance(value, Mapping) or set(value) != {'calendar_id', 'revision', 'timezone', 'week_rule', 'date_map'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return validate_calendar(ReportingCalendar(
        _text(value['calendar_id']), _positive_int(value['revision'], 'REPORT_ARTIFACT_INVALID'),
        _text(value['timezone']), value['week_rule'], value['date_map'],
    ))


def _selection_from_mapping(value):
    if not isinstance(value, Mapping) or set(value) != {'template_id', 'revision', 'revision_hash', 'origin'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return _template_selection(UserTemplateSelection(
        validate_uuid_text(value['template_id']), _positive_int(value['revision'], 'REPORT_ARTIFACT_INVALID'),
        validate_hash_text(value['revision_hash']), value['origin'],
    ))


def _template_selection(value):
    if not isinstance(value, UserTemplateSelection) or value.origin != 'user':
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return UserTemplateSelection(validate_uuid_text(value.template_id), _positive_int(value.revision, 'REPORT_INVALID'), validate_hash_text(value.revision_hash))


def _name(value):
    value = _text(value)
    if not value or len(value) > 160:
        raise ReportError('REPORT_INVALID')
    return value


def _text(value):
    if type(value) is not str:
        raise ReportError('REPORT_INVALID')
    return value


def _positive_int(value, code):
    if type(value) is not int or value < 1:
        raise ReportError(code)
    return value
