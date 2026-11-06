from dataclasses import dataclass, field
from typing import Literal, Mapping
from uuid import UUID

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring_fragments import (
    plain_text_fragment,
    rich_text_fragment_plain_text,
    validate_rich_text_fragment,
)
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_edits import validate_edit_targets
from project_management.app.domain.report_presentation import ReportEdit, TemplateSelection
from project_management.app.domain.report_templates import UserTemplateSelection, validate_template_document_snapshot


AUTHORING_SCHEMA = 'report-authoring/2'
AUTHORING_BUILTIN_VERSION = '2'
MAX_TOTAL_AUTHORED_EDIT_BYTES = 1_048_576
BUILTIN_TEMPLATE_IDS = {'daily-standup', 'weekly-timeline'}


@dataclass(frozen=True, slots=True)
class AuthoringTemplateSelection:
    origin: Literal['builtin', 'user']
    template_id: str
    version: str
    options: Mapping = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthoredEditRequest:
    edit_id: str
    kind: Literal['note', 'narrative_override', 'slot_fill']
    target: Mapping
    fragment: Mapping
    expected_original_hash: str | None = None
    reference_receipts: tuple = ()
    assist_receipt_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthoredEdit:
    edit_id: str
    kind: Literal['note', 'narrative_override', 'slot_fill']
    target: Mapping
    fragment: Mapping
    expected_original_hash: str | None
    author: str
    edited_at: str
    origin: Literal['human', 'ai_assisted'] = 'human'
    source_ai_result_ref: Mapping | None = None
    reference_observations: tuple = ()


def normalize_authoring_template_selection(template) -> TemplateSelection:
    if not isinstance(template, AuthoringTemplateSelection):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if template.origin != 'builtin':
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if (type(template.template_id) is not str
            or type(template.version) is not str
            or not isinstance(template.options, Mapping)
            or template.template_id not in BUILTIN_TEMPLATE_IDS
            or template.version != AUTHORING_BUILTIN_VERSION):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if any(type(key) is not str for key in template.options):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return TemplateSelection(template.template_id, template.version, dict(template.options))


def user_template_selection(template) -> UserTemplateSelection | None:
    if isinstance(template, UserTemplateSelection) and template.origin == 'user':
        return template
    return None


def authored_successor_selection(template: TemplateSelection) -> tuple[AuthoringTemplateSelection, TemplateSelection]:
    if template.template_id not in BUILTIN_TEMPLATE_IDS:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    authoring = AuthoringTemplateSelection('builtin', template.template_id, AUTHORING_BUILTIN_VERSION, dict(template.options))
    return authoring, TemplateSelection(template.template_id, AUTHORING_BUILTIN_VERSION, dict(template.options))


def template_snapshot(template: AuthoringTemplateSelection, normalized: TemplateSelection, definition):
    fill_policy = {'schema_version': 1, 'instructions': {}}
    resolved_document = {
        'schema_version': 1,
        'report_kind': 'weekly' if normalized.template_id == 'weekly-timeline' else 'daily',
        'blocks': (),
        'compatibility': 'schema1-renderer',
    }
    return {
        'selection': {
            'origin': template.origin,
            'template_id': normalized.template_id,
            'version': normalized.version,
            'options': dict(definition.options),
        },
        'resolved_document': resolved_document,
        'presentation_hash': definition.template_hash,
        'fill_policy': fill_policy,
        'fill_policy_hash': _hash(fill_policy),
        'renderer_version': definition.renderer_version,
    }


def validate_template_snapshot(value):
    expected = {
        'selection', 'resolved_document', 'presentation_hash', 'fill_policy',
        'fill_policy_hash', 'renderer_version',
    }
    if not isinstance(value, Mapping) or set(value.keys()) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['fill_policy_hash'] != _hash(value['fill_policy']):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['renderer_version'] == 'template-document/1':
        return validate_template_document_snapshot(value)
    return {
        'selection': _json_mapping(value['selection']),
        'resolved_document': _json_mapping(value['resolved_document']),
        'presentation_hash': _hash_text(value['presentation_hash']),
        'fill_policy': _json_mapping(value['fill_policy']),
        'fill_policy_hash': _hash_text(value['fill_policy_hash']),
        'renderer_version': _str(value['renderer_version']),
    }


def attributed_authored_edits(snapshot, current_edits, requested_edits, actor_subject: str, timestamp: str,
                              reference_observations=None, template_snapshot=None) -> tuple[AuthoredEdit, ...]:
    requests = validate_authored_edit_requests(snapshot, requested_edits, template_snapshot)
    previous = {edit.edit_id: edit for edit in current_edits}
    reference_observations = reference_observations or {}
    attributed = []
    for request in requests:
        old = previous.get(request.edit_id)
        observations = tuple(reference_observations.get(request.edit_id, ()))
        if old is not None and _same_content(old, request) and old.reference_observations == observations:
            attributed.append(old)
        else:
            attributed.append(AuthoredEdit(
                request.edit_id, request.kind, request.target, request.fragment,
                request.expected_original_hash, actor_subject, timestamp,
                reference_observations=observations,
            ))
    _total_size(attributed)
    return tuple(attributed)


def validate_authored_edit_requests(snapshot, edits, template_snapshot=None) -> tuple[AuthoredEditRequest, ...]:
    requests = tuple(_request(item) for item in tuple(edits or ()))
    _unique_edit_ids(requests)
    legacy = tuple(_legacy_validation_edit(request) for request in requests if request.kind != 'slot_fill')
    validate_edit_targets(snapshot, legacy)
    _validate_slot_fills(requests, template_snapshot)
    _total_size(requests)
    return requests


def validate_authored_edits(snapshot, edits, template_snapshot=None) -> tuple[AuthoredEdit, ...]:
    authored = tuple(_authored_edit(item) for item in tuple(edits or ()))
    _unique_edit_ids(authored)
    legacy = tuple(_legacy_validation_edit(edit) for edit in authored if edit.kind != 'slot_fill')
    validate_edit_targets(snapshot, legacy)
    _validate_slot_fills(authored, template_snapshot)
    _total_size(authored)
    return authored


def authored_edit_from_mapping(value) -> AuthoredEdit:
    expected = {
        'edit_id', 'kind', 'target', 'fragment', 'expected_original_hash', 'author',
        'edited_at', 'origin', 'source_ai_result_ref', 'reference_observations',
    }
    if not isinstance(value, Mapping) or set(value.keys()) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return AuthoredEdit(
        _uuid(value['edit_id']),
        _literal(value['kind'], {'note', 'narrative_override', 'slot_fill'}, 'REPORT_ARTIFACT_INVALID'),
        _json_mapping(value['target']),
        validate_rich_text_fragment(value['fragment']),
        _optional_hash(value['expected_original_hash'], 'REPORT_ARTIFACT_INVALID'),
        _str(value['author']),
        _str(value['edited_at']),
        _literal(value['origin'], {'human', 'ai_assisted'}, 'REPORT_ARTIFACT_INVALID'),
        None if value['source_ai_result_ref'] is None else _json_mapping(value['source_ai_result_ref']),
        tuple(_json_mapping(item) for item in _list(value['reference_observations'], 'REPORT_ARTIFACT_INVALID')),
    )


def authored_edit_request_payload(edit) -> Mapping:
    request = _request(edit)
    return {
        'edit_id': request.edit_id,
        'kind': request.kind,
        'target': request.target,
        'fragment': request.fragment,
        'expected_original_hash': request.expected_original_hash,
        'reference_receipts': request.reference_receipts,
        'assist_receipt_id': request.assist_receipt_id,
    }


def legacy_edit_to_authored(edit: ReportEdit) -> AuthoredEdit:
    return AuthoredEdit(
        edit.edit_id, edit.kind, edit.target, plain_text_fragment(edit.text),
        edit.expected_original_hash, edit.author or '', edit.edited_at or '',
    )


def authored_edit_to_legacy(edit: AuthoredEdit) -> ReportEdit:
    return ReportEdit(
        edit.edit_id,
        edit.kind,
        edit.target,
        rich_text_fragment_plain_text(edit.fragment),
        edit.expected_original_hash,
        edit.author,
        edit.edited_at,
    )


def _request(value) -> AuthoredEditRequest:
    if not isinstance(value, AuthoredEditRequest):
        raise ReportError('REPORT_INVALID')
    reference_receipts = tuple(value.reference_receipts or ())
    if any(type(receipt) is not str for receipt in reference_receipts):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    assist_id = None if value.assist_receipt_id is None else _uuid(value.assist_receipt_id, 'REPORT_EDIT_TARGET_INVALID')
    return AuthoredEditRequest(
        _uuid(value.edit_id, 'REPORT_EDIT_TARGET_INVALID'),
        _literal(value.kind, {'note', 'narrative_override', 'slot_fill'}, 'REPORT_EDIT_TARGET_INVALID'),
        _json_mapping(value.target, 'REPORT_EDIT_TARGET_INVALID'),
        validate_rich_text_fragment(value.fragment),
        _optional_hash(value.expected_original_hash, 'REPORT_EDIT_TARGET_INVALID'),
        reference_receipts,
        assist_id,
    )


def _authored_edit(value) -> AuthoredEdit:
    if isinstance(value, AuthoredEdit):
        return AuthoredEdit(
            _uuid(value.edit_id, 'REPORT_ARTIFACT_INVALID'),
            _literal(value.kind, {'note', 'narrative_override', 'slot_fill'}, 'REPORT_ARTIFACT_INVALID'),
            _json_mapping(value.target),
            validate_rich_text_fragment(value.fragment),
            _optional_hash(value.expected_original_hash, 'REPORT_ARTIFACT_INVALID'),
            _str(value.author),
            _str(value.edited_at),
            _literal(value.origin, {'human', 'ai_assisted'}, 'REPORT_ARTIFACT_INVALID'),
            None if value.source_ai_result_ref is None else _json_mapping(value.source_ai_result_ref),
            tuple(_json_mapping(item) for item in tuple(value.reference_observations or ())),
        )
    return authored_edit_from_mapping(value)


def _legacy_validation_edit(edit) -> ReportEdit:
    return ReportEdit(edit.edit_id, edit.kind, edit.target, 'x', edit.expected_original_hash)


def _unique_edit_ids(edits) -> None:
    seen = set()
    for edit in edits:
        if edit.edit_id in seen:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        seen.add(edit.edit_id)


def _validate_slot_fills(edits, template_snapshot) -> None:
    slot_edits = [edit for edit in edits if edit.kind == 'slot_fill']
    if not slot_edits:
        return
    if template_snapshot is None:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    snapshot = validate_template_document_snapshot(template_snapshot)
    slots = {block['slot_id'] for block in snapshot['resolved_document']['blocks'] if block['kind'] == 'slot'}
    seen_slots = set()
    for edit in slot_edits:
        if edit.expected_original_hash is not None or set(edit.target) != {'scope', 'slot_id'}:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        if edit.target['scope'] != 'template_slot' or edit.target['slot_id'] not in slots:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        if edit.target['slot_id'] in seen_slots:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        seen_slots.add(edit.target['slot_id'])


def _same_content(old: AuthoredEdit, request: AuthoredEditRequest) -> bool:
    return (
        old.edit_id == request.edit_id
        and old.kind == request.kind
        and old.target == request.target
        and old.fragment == request.fragment
        and old.expected_original_hash == request.expected_original_hash
    )


def _total_size(edits) -> None:
    try:
        size = len(canonical_bytes(tuple(edits)))
    except ArchiveError:
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    if size > MAX_TOTAL_AUTHORED_EDIT_BYTES:
        raise ReportError('REPORT_LIMIT')


def _hash(value) -> str:
    return sha256_bytes(canonical_bytes(value))


def _hash_text(value: str) -> str:
    if type(value) is not str or len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _optional_hash(value, code='REPORT_ARTIFACT_INVALID'):
    if value is None:
        return None
    if type(value) is not str or len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
        raise ReportError(code)
    return value


def _uuid(value, code='REPORT_ARTIFACT_INVALID') -> str:
    if type(value) is not str:
        raise ReportError(code)
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ReportError(code) from None
    if str(parsed) != value.lower():
        raise ReportError(code)
    return value


def _literal(value, allowed, code):
    if type(value) is not str or value not in allowed:
        raise ReportError(code)
    return value


def _str(value) -> str:
    if type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _json_mapping(value, code='REPORT_ARTIFACT_INVALID'):
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise ReportError(code)
    return {key: _json_value(item, code) for key, item in value.items()}


def _json_value(value, code='REPORT_ARTIFACT_INVALID'):
    if value is None or type(value) in {str, int, bool, float}:
        return value
    if isinstance(value, Mapping):
        return _json_mapping(value, code)
    if isinstance(value, list):
        return tuple(_json_value(item, code) for item in value)
    if isinstance(value, tuple):
        return tuple(_json_value(item, code) for item in value)
    raise ReportError(code)


def _list(value, code):
    if not isinstance(value, list):
        raise ReportError(code)
    return value
