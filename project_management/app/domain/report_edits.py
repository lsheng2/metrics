from dataclasses import dataclass
import hashlib
from typing import Mapping
from uuid import UUID

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError, ReportSourceSnapshot
from project_management.app.domain.report_presentation import ReportEdit


MAX_EDIT_TEXT_BYTES = 16_384
MAX_TOTAL_EDITS_BYTES = 1_048_576
ISSUE_FIELDS = {'what', 'current_position', 'verification'}
ACTION_FIELDS = {'action', 'owner_display'}
MESSAGE_FIELDS = {'text'}


@dataclass(frozen=True, slots=True)
class _TargetResolution:
    target_key: tuple
    original_text: str | None


def validate_edit_targets(snapshot: ReportSourceSnapshot, edits) -> tuple[ReportEdit, ...]:
    edit_tuple = tuple(edits or ())
    seen_ids = set()
    seen_overrides = set()
    for edit in edit_tuple:
        _validate_edit_id(edit, seen_ids)
        _validate_text(edit.text)
        resolution = _resolve_target(snapshot, edit.target, edit.kind, fail=True)
        if edit.kind == 'narrative_override':
            _validate_override(edit, resolution, seen_overrides)
        elif edit.kind == 'note':
            if edit.expected_original_hash is not None:
                raise ReportError('REPORT_EDIT_TARGET_INVALID')
        else:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    _enforce_total_edit_size(edit_tuple)
    return edit_tuple


def original_target_text(snapshot: ReportSourceSnapshot, target) -> str | None:
    resolution = _resolve_target(snapshot, target, None, fail=False)
    return None if resolution is None else resolution.original_text


def source_key_hash(source_key) -> str:
    return hashlib.sha256(canonical_bytes(source_key)).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _validate_override(edit: ReportEdit, resolution: _TargetResolution, seen_overrides: set) -> None:
    if resolution.original_text is None:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if edit.expected_original_hash != text_hash(resolution.original_text):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if resolution.target_key in seen_overrides:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    seen_overrides.add(resolution.target_key)


def _validate_edit_id(edit: ReportEdit, seen_ids: set) -> None:
    try:
        parsed = UUID(edit.edit_id)
    except (TypeError, ValueError, AttributeError):
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    if str(parsed) != edit.edit_id.lower():
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if edit.edit_id in seen_ids:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    seen_ids.add(edit.edit_id)


def _validate_text(value: str) -> None:
    if type(value) is not str or value == '':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError:
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    if size > MAX_EDIT_TEXT_BYTES:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    for character in value:
        codepoint = ord(character)
        if codepoint < 32 and character not in {'\n', '\r', '\t'}:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _enforce_total_edit_size(edits: tuple[ReportEdit, ...]) -> None:
    try:
        size = len(canonical_bytes(edits))
    except (ArchiveError, UnicodeError):
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    if size > MAX_TOTAL_EDITS_BYTES:
        raise ReportError('REPORT_LIMIT')


def _resolve_target(snapshot: ReportSourceSnapshot, target, kind: str | None, *, fail: bool):
    try:
        return _resolve_target_strict(snapshot, target, kind)
    except ReportError:
        if fail:
            raise
        return None


def _resolve_target_strict(snapshot: ReportSourceSnapshot, target, kind: str | None) -> _TargetResolution:
    if not isinstance(target, Mapping) or type(target.get('scope')) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    scope = target['scope']
    if scope == 'report':
        return _resolve_report_target(target, kind)
    if scope == 'issue':
        return _resolve_issue_target(snapshot, target, kind)
    if scope == 'action':
        return _resolve_action_target(snapshot, target, kind)
    if scope == 'message':
        return _resolve_message_target(snapshot, target, kind)
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _resolve_report_target(target: Mapping, kind: str | None) -> _TargetResolution:
    if set(target.keys()) != {'scope'} or kind == 'narrative_override':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return _TargetResolution(('report',), None)


def _resolve_issue_target(snapshot: ReportSourceSnapshot, target: Mapping, kind: str | None) -> _TargetResolution:
    keys = set(target.keys())
    if keys == {'scope', 'source_key_hash'}:
        if kind == 'narrative_override':
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        row = _find_row(snapshot, target['source_key_hash'])
        return _TargetResolution(('issue-note', target['source_key_hash']), None if row else None)
    if keys == {'scope', 'source_key_hash', 'field'}:
        if kind == 'note' or target['field'] not in ISSUE_FIELDS:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        row = _find_row(snapshot, target['source_key_hash'])
        value = getattr(row, target['field'])
        return _TargetResolution(('issue', target['source_key_hash'], target['field']), _string_or_empty(value))
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _resolve_action_target(snapshot: ReportSourceSnapshot, target: Mapping, kind: str | None) -> _TargetResolution:
    keys = set(target.keys())
    base_keys = {'scope', 'source_key_hash', 'summary_id', 'action_index'}
    if keys == base_keys:
        if kind == 'narrative_override':
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        _find_action(snapshot, target)
        return _TargetResolution(_action_key(target, 'note'), None)
    if keys == base_keys | {'field'}:
        if kind == 'note' or target['field'] not in ACTION_FIELDS:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        action = _find_action(snapshot, target)
        return _TargetResolution(_action_key(target, target['field']), _action_field_text(action, target['field']))
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _resolve_message_target(snapshot: ReportSourceSnapshot, target: Mapping, kind: str | None) -> _TargetResolution:
    if set(target.keys()) != {'scope', 'message_id', 'field'}:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if kind == 'note' or target['field'] not in MESSAGE_FIELDS:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    matches = [message for message in snapshot.key_messages if message.message_id == target['message_id']]
    if len(matches) != 1:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return _TargetResolution(('message', target['message_id'], 'text'), matches[0].text)


def _find_row(snapshot: ReportSourceSnapshot, expected_hash: str):
    matches = [row for row in snapshot.rows if source_key_hash(row.source_key) == expected_hash]
    if len(matches) != 1:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return matches[0]


def _find_action(snapshot: ReportSourceSnapshot, target: Mapping):
    if type(target.get('summary_id')) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if type(target.get('action_index')) is not int or target['action_index'] < 0:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    row = _find_row(snapshot, target['source_key_hash'])
    if row.summary_ref is None or row.summary_ref.summary_id != target['summary_id']:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    try:
        return row.next_actions[target['action_index']]
    except IndexError:
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None


def _action_key(target: Mapping, field: str) -> tuple:
    return (
        'action',
        target['source_key_hash'],
        target['summary_id'],
        target['action_index'],
        field,
    )


def _string_or_empty(value) -> str:
    return '' if value is None else str(value)


def _action_field_text(action: Mapping, field: str) -> str:
    if field == 'owner_display':
        return _owner_display(action)
    return _string_or_empty(action.get(field))


def _owner_display(action: Mapping) -> str:
    for field in ('owner_display', 'ownerDisplay', 'displayName', 'owner_id'):
        value = action.get(field)
        if type(value) is str and value:
            return value
    return ''
