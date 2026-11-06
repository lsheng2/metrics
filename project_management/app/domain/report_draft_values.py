from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Mapping
from uuid import UUID

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import SourceChainKey, WorkItemIdentity
from project_management.app.domain.report_contracts import (
    ReportDay,
    ReportError,
    ReportEvent,
    ReportMessage,
    ReportRow,
    ReportSelection,
    ReportSourceSnapshot,
    SummaryReference,
)
from project_management.app.domain.report_authoring import AUTHORING_SCHEMA, AuthoredEdit, authored_edit_from_mapping, validate_template_snapshot
from project_management.app.domain.report_authoring_revision import validate_revision_authoring_context
from project_management.app.domain.report_presentation import ReportEdit, TemplateDefinition, TemplateSelection


MAX_COLLECTION = 10000


@dataclass(frozen=True, slots=True)
class ReportDraftLimits:
    max_edit_history_bytes: int = 8_388_608
    max_revisions: int = 1000


@dataclass(frozen=True, slots=True)
class ReportDraft:
    draft_id: str
    revision: int
    revision_hash: str
    selection: ReportSelection
    snapshot_hash: str
    snapshot: ReportSourceSnapshot
    template: TemplateSelection
    template_definition: TemplateDefinition
    edits: tuple[ReportEdit, ...]
    created_at: str
    updated_at: str
    parent_publication_id: str | None
    state: Literal['draft', 'finalizing', 'finalized']
    authoring_schema: str | None = None
    template_snapshot: Mapping | None = None
    authored_edits: tuple[AuthoredEdit, ...] = ()
    authoring_context: Mapping | None = None
    preservation_review_issues: tuple[Mapping, ...] = ()


@dataclass(frozen=True, slots=True)
class ReportDraftSummary:
    draft_id: str
    revision: int
    revision_hash: str
    source_as_of: str
    updated_at: str
    state: Literal['draft', 'finalizing', 'finalized']
    template_id: str
    parent_publication_id: str | None
    preservation_review_issues: tuple[Mapping, ...] = ()


@dataclass(frozen=True, slots=True)
class ReportDraftPage:
    items: tuple[ReportDraftSummary, ...]
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class ReportPublicationPage:
    items: tuple['ReportPublication', ...]
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class ReportArchiveTarget:
    archive_id: str
    project_id: str
    stage_id: str


@dataclass(frozen=True, slots=True)
class ReportFinalizationStatus:
    draft_id: str
    state: Literal['finalizing', 'finalized']
    command_id: str
    publication_id: str
    draft_revision: int


def canonical_hash(value) -> str:
    return sha256_bytes(canonical_bytes(value))


def bytes_hash(data: bytes) -> str:
    return sha256_bytes(data)


def read_json(data: bytes):
    return decode_json(data)


def validate_uuid_text(value: str) -> str:
    if type(value) is not str:
        raise ReportError('REPORT_INVALID')
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ReportError('REPORT_INVALID') from None
    if str(parsed) != value.lower():
        raise ReportError('REPORT_INVALID')
    return value


def validate_hash_text(value: str) -> str:
    if type(value) is not str or len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def validate_git_commit_text(value: str) -> str:
    if type(value) is not str or len(value) != 40 or any(character not in '0123456789abcdef' for character in value):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def validate_time_text(value: str) -> str:
    if type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def validate_date_text(value: str) -> str:
    if type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
    return value


def selection_from_mapping(value) -> ReportSelection:
    _keys(value, {'capture_id', 'baseline_publication_id', 'parent_publication_id', 'purpose', 'timezone'})
    return ReportSelection(
        validate_uuid_text(value['capture_id']),
        _optional_uuid(value['baseline_publication_id']),
        _optional_uuid(value['parent_publication_id']),
        _literal(value['purpose'], {'standup', 'historical_export'}),
        _str(value['timezone']),
    )


def template_selection_from_mapping(value) -> TemplateSelection:
    _keys(value, {'template_id', 'version', 'options'})
    return TemplateSelection(_str(value['template_id']), _str(value['version']), _json_mapping(value['options']))


def template_definition_from_mapping(value) -> TemplateDefinition:
    _keys(value, {'template_id', 'version', 'options', 'template_hash', 'renderer_version'})
    return TemplateDefinition(
        _str(value['template_id']),
        _str(value['version']),
        _json_mapping(value['options']),
        validate_hash_text(value['template_hash']),
        _str(value['renderer_version']),
    )


def edit_from_mapping(value) -> ReportEdit:
    _keys(value, {'edit_id', 'kind', 'target', 'text', 'expected_original_hash', 'author', 'edited_at'})
    return ReportEdit(
        validate_uuid_text(value['edit_id']),
        _literal(value['kind'], {'note', 'narrative_override'}),
        _json_mapping(value['target']),
        _str(value['text']),
        _optional_hash(value['expected_original_hash']),
        _str(value['author']),
        validate_time_text(value['edited_at']),
    )


def snapshot_from_mapping(value) -> ReportSourceSnapshot:
    _keys(value, {
        'schema_version', 'project_id', 'stage_id', 'project_name', 'stage_name', 'owner_subject',
        'rule_hash', 'source_commit', 'capture_id', 'source_as_of', 'report_date', 'timezone',
        'baseline_publication_id', 'comparison_policy_hash', 'coverage', 'key_messages', 'rows',
        'events', 'days',
    })
    return ReportSourceSnapshot(
        _literal(value['schema_version'], {1}),
        validate_uuid_text(value['project_id']),
        validate_uuid_text(value['stage_id']),
        _str(value['project_name']),
        _str(value['stage_name']),
        _str(value['owner_subject']),
        validate_hash_text(value['rule_hash']),
        validate_git_commit_text(value['source_commit']),
        validate_uuid_text(value['capture_id']),
        validate_time_text(value['source_as_of']),
        validate_date_text(value['report_date']),
        _str(value['timezone']),
        _optional_uuid(value['baseline_publication_id']),
        validate_hash_text(value['comparison_policy_hash']),
        _json_mapping(value['coverage']),
        tuple(message_from_mapping(item) for item in _list(value['key_messages'])),
        tuple(row_from_mapping(item) for item in _list(value['rows'])),
        tuple(event_from_mapping(item) for item in _list(value['events'])),
        tuple(day_from_mapping(item) for item in _list(value['days'])),
    )


def message_from_mapping(value) -> ReportMessage:
    _keys(value, {'message_id', 'text', 'source_refs'})
    return ReportMessage(_str(value['message_id']), _str(value['text']), tuple(_str(item) for item in _list(value['source_refs'])))


def row_from_mapping(value) -> ReportRow:
    _keys(value, {
        'source_key', 'identity', 'title', 'status', 'assignee', 'source_url', 'source_hash',
        'coverage', 'summary_ref', 'what', 'current_position', 'verification', 'next_actions',
        'blocker_refs', 'limitation_refs', 'evidence', 'summary_as_of', 'pending_reason',
    })
    return ReportRow(
        source_key_from_mapping(value['source_key']),
        identity_from_mapping(value['identity']),
        _optional_str(value['title']),
        _optional_str(value['status']),
        _json_value(value['assignee']),
        _optional_str(value['source_url']),
        _optional_hash(value['source_hash']),
        _json_mapping(value['coverage']),
        None if value['summary_ref'] is None else summary_ref_from_mapping(value['summary_ref']),
        _optional_str(value['what']),
        _optional_str(value['current_position']),
        _optional_str(value['verification']),
        tuple(_json_mapping(item) for item in _list(value['next_actions'])),
        tuple(_str(item) for item in _list(value['blocker_refs'])),
        tuple(_str(item) for item in _list(value['limitation_refs'])),
        tuple(_json_mapping(item) for item in _list(value['evidence'])),
        None if value['summary_as_of'] is None else validate_time_text(value['summary_as_of']),
        _optional_str(value['pending_reason']),
    )


def event_from_mapping(value) -> ReportEvent:
    _keys(value, {'event_id', 'source_key', 'kind', 'before', 'after', 'occurred_at', 'observed_at', 'source_refs'})
    return ReportEvent(
        _str(value['event_id']),
        source_key_from_mapping(value['source_key']),
        _str(value['kind']),
        None if value['before'] is None else _json_mapping(value['before']),
        None if value['after'] is None else _json_mapping(value['after']),
        None if value['occurred_at'] is None else validate_time_text(value['occurred_at']),
        validate_time_text(value['observed_at']),
        tuple(_str(item) for item in _list(value['source_refs'])),
    )


def day_from_mapping(value) -> ReportDay:
    _keys(value, {'report_date', 'publication_id', 'state', 'source_as_of', 'coverage', 'rows', 'events'})
    return ReportDay(
        validate_date_text(value['report_date']),
        _optional_uuid(value['publication_id']),
        _literal(value['state'], {'published', 'no_publication'}),
        None if value['source_as_of'] is None else validate_time_text(value['source_as_of']),
        _json_mapping(value['coverage']),
        tuple(row_from_mapping(item) for item in _list(value['rows'])),
        tuple(event_from_mapping(item) for item in _list(value['events'])),
    )


def summary_ref_from_mapping(value) -> SummaryReference:
    _keys(value, {'summary_id', 'revision', 'target_capture_id', 'source_hash', 'input_hash', 'result_hash', 'owning_commit'})
    return SummaryReference(
        _str(value['summary_id']),
        _positive_int(value['revision']),
        validate_uuid_text(value['target_capture_id']),
        validate_hash_text(value['source_hash']),
        validate_hash_text(value['input_hash']),
        validate_hash_text(value['result_hash']),
        validate_git_commit_text(value['owning_commit']),
    )


def source_key_from_mapping(value) -> SourceChainKey:
    _keys(value, {'provider_id', 'endpoint_id', 'stable_id', 'principal_id', 'rule_hash'})
    return SourceChainKey(_str(value['provider_id']), _str(value['endpoint_id']), _str(value['stable_id']),
                          _str(value['principal_id']), validate_hash_text(value['rule_hash']))


def identity_from_mapping(value) -> WorkItemIdentity:
    _keys(value, {'provider_id', 'endpoint_id', 'stable_id', 'display_key'})
    return WorkItemIdentity(_str(value['provider_id']), _str(value['endpoint_id']), _str(value['stable_id']), _str(value['display_key']))


def revision_from_mapping(value):
    if not isinstance(value, Mapping):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    schema_version = value.get('schema_version')
    if schema_version == 2:
        return _authored_revision_from_mapping(value)
    _keys(value, {
        'schema_version', 'draft_id', 'revision', 'selection', 'snapshot_hash', 'template',
        'template_definition', 'edits', 'created_at', 'updated_at', 'parent_publication_id',
    })
    return {
        'schema_version': _literal(value['schema_version'], {1}),
        'draft_id': validate_uuid_text(value['draft_id']),
        'revision': _positive_int(value['revision']),
        'selection': selection_from_mapping(value['selection']),
        'snapshot_hash': validate_hash_text(value['snapshot_hash']),
        'template': template_selection_from_mapping(value['template']),
        'template_definition': template_definition_from_mapping(value['template_definition']),
        'edits': tuple(edit_from_mapping(item) for item in _list(value['edits'])),
        'created_at': validate_time_text(value['created_at']),
        'updated_at': validate_time_text(value['updated_at']),
        'parent_publication_id': _optional_uuid(value['parent_publication_id']),
    }


def _authored_revision_from_mapping(value):
    _keys(value, {
        'schema_version', 'draft_id', 'revision', 'selection', 'snapshot_hash', 'template',
        'template_definition', 'edits', 'created_at', 'updated_at', 'parent_publication_id',
        'authoring_schema', 'template_snapshot', 'authoring_context',
    })
    return {
        'schema_version': _literal(value['schema_version'], {2}),
        'draft_id': validate_uuid_text(value['draft_id']),
        'revision': _positive_int(value['revision']),
        'selection': selection_from_mapping(value['selection']),
        'snapshot_hash': validate_hash_text(value['snapshot_hash']),
        'template': template_selection_from_mapping(value['template']),
        'template_definition': template_definition_from_mapping(value['template_definition']),
        'edits': tuple(authored_edit_from_mapping(item) for item in _list(value['edits'])),
        'created_at': validate_time_text(value['created_at']),
        'updated_at': validate_time_text(value['updated_at']),
        'parent_publication_id': _optional_uuid(value['parent_publication_id']),
        'authoring_schema': _literal(value['authoring_schema'], {AUTHORING_SCHEMA}),
        'template_snapshot': validate_template_snapshot(value['template_snapshot']),
        'authoring_context': validate_revision_authoring_context(value['authoring_context'], value['template_snapshot']),
    }

def _keys(value, expected: set[str]) -> None:
    if not isinstance(value, Mapping) or set(value.keys()) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')

def _str(value) -> str:
    if type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value

def _optional_str(value) -> str | None:
    return None if value is None else _str(value)

def _optional_uuid(value) -> str | None:
    return None if value is None else validate_uuid_text(value)

def _optional_hash(value) -> str | None:
    return None if value is None else validate_hash_text(value)

def _positive_int(value) -> int:
    if type(value) is not int or value < 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value

def _literal(value, allowed):
    if all(type(value) is not type(item) for item in allowed) or value not in allowed:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value

def _list(value) -> list:
    if not isinstance(value, list) or len(value) > MAX_COLLECTION:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value

def _json_mapping(value) -> Mapping:
    if not isinstance(value, Mapping) or len(value) > MAX_COLLECTION or any(type(key) is not str for key in value):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {key: _json_value(item) for key, item in value.items()}

def _json_value(value):
    if value is None or type(value) in {str, int, bool, float}:
        return value
    if isinstance(value, Mapping):
        return _json_mapping(value)
    if isinstance(value, list):
        return tuple(_json_value(item) for item in _list(value))
    raise ReportError('REPORT_ARTIFACT_INVALID')
