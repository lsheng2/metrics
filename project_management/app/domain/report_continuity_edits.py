from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring import AuthoredEdit, AuthoredEditRequest, authored_edit_from_mapping
from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text, validate_rich_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_workflow_changes import (
    COMMAND_FIELDS, apply_workflow_change, is_human_action, touch_action,
)


def apply_continuity_edit_requests(context, active_edits, requested_edits, actor_subject, timestamp, reference_observations=None):
    context = validate_daily_authoring_context(context)
    requests = tuple(_request(item) for item in tuple(requested_edits or ()))
    _unique(edit.edit_id for edit in requests)
    previous = {edit.edit_id: edit for edit in tuple(active_edits or ())}
    reference_observations = reference_observations or {}
    updated = context
    for request in requests:
        old = previous.get(request.edit_id)
        if old is not None and _same_content(old, request):
            continue
        updated = _apply_continuity_edit(updated, request, actor_subject, timestamp)
    validate_daily_authoring_context(updated)
    return updated, tuple(_attribute(active_edits, request, actor_subject, timestamp, reference_observations) for request in requests)


def apply_continuity_changes(context, changes, actor_subject, timestamp):
    context = validate_daily_authoring_context(context)
    updated = context
    for change in tuple(changes or ()):
        updated = _apply_change(updated, _change(change), actor_subject, timestamp)
        validate_daily_authoring_context(updated)
    return updated


def validate_continuity_authored_edits(context, edits):
    context = validate_daily_authoring_context(context)
    authored = tuple(_authored(edit) for edit in tuple(edits or ()))
    _unique(edit.edit_id for edit in authored)
    observations = {item['note_id'] for item in context['current_observations']}
    for edit in authored:
        if edit.kind != 'note':
            raise ReportError('REPORT_ARTIFACT_INVALID')
        scope = edit.target.get('scope') if isinstance(edit.target, Mapping) else None
        if scope == 'daily_note' and _daily_note_target(edit.target) not in observations:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        elif scope == 'persistent_note' and not any(note['note_id'] == edit.target.get('note_id') for note in context['persistent_notes']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        elif scope == 'report_action' and not any(action['action_id'] == edit.target.get('action_id') for action in context['actions']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        elif scope not in {'daily_note', 'persistent_note', 'report_action'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        validate_rich_text_fragment(edit.fragment)
    return authored


def _apply_change(context, change, actor_subject, timestamp):
    kind = change['kind']
    if kind in COMMAND_FIELDS:
        return apply_workflow_change(context, change, actor_subject, timestamp)
    if kind == 'add_persistent_note':
        return _add_persistent_note(context, change, actor_subject, timestamp)
    if kind == 'set_persistent_carry':
        return _set_persistent_carry(context, change)
    if kind == 'set_action_tracking':
        return _set_action_tracking(context, change, actor_subject, timestamp)
    if kind == 'move_row':
        return _move_row(context, change)
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _add_persistent_note(context, change, actor_subject, timestamp):
    note_id = validate_uuid_text(change['note_id'])
    if any(note['note_id'] == note_id for note in context['persistent_notes']):
        raise ReportError('REPORT_REVISION_CONFLICT')
    target = change['target']
    issue_ref = change['issue_ref']
    if target == 'report':
        if issue_ref is not None:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    elif target == 'issue':
        issue_ref = _issue_ref(issue_ref)
        _require_row(context, issue_ref)
    else:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    note = {
        'note_id': note_id,
        'target': target,
        'issue_ref': issue_ref,
        'fragment': validate_rich_text_fragment(change['fragment']),
        'revision': 1,
        'carry_forward': _bool(change['carry_forward']),
        'provenance': {'origin': 'human', 'edited_by': actor_subject, 'edited_at': timestamp},
    }
    return {**context, 'persistent_notes': (*context['persistent_notes'], note)}


def _set_persistent_carry(context, change):
    note_id = validate_uuid_text(change['note_id'])
    found = False
    notes = []
    for note in context['persistent_notes']:
        if note['note_id'] == note_id:
            found = True
            notes.append({**note, 'carry_forward': _bool(change['carry_forward'])})
        else:
            notes.append(note)
    if not found:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {**context, 'persistent_notes': tuple(notes)}


def _set_action_tracking(context, change, actor_subject, timestamp):
    action_id = validate_uuid_text(change['action_id'])
    state = _literal(change['state'], {'open', 'done', 'canceled', 'unknown'})
    expected = _literal(change['expected_state'], {'open', 'done', 'canceled', 'unknown'})
    actions = []
    found = False
    for action in context['actions']:
        if action['action_id'] != action_id:
            actions.append(action)
            continue
        found = True
        if action['tracking_state'] != expected:
            raise ReportError('REPORT_REVISION_CONFLICT')
        evidence_refs = tuple(_str(item) for item in tuple(change['evidence_refs']))
        if state in {'done', 'canceled'} and (
                not rich_text_fragment_plain_text(change['resolution']).strip()
                or not is_human_action(action) and not evidence_refs):
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        if any(item not in action['evidence_refs'] for item in evidence_refs):
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        actions.append(touch_action({**action, 'tracking_state': state, 'resolution': {
            'fragment': validate_rich_text_fragment(change['resolution']),
            'evidence_refs': evidence_refs,
            'resolved_by': actor_subject,
            'resolved_at': timestamp,
        }}, actor_subject, timestamp))
    if not found:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {**context, 'actions': tuple(actions), 'weekly_seed': {
        **context['weekly_seed'], 'unresolved_action_ids': tuple(
            item['action_id'] for item in actions if item['tracking_state'] not in {'done', 'canceled'}
        ),
    }}


def _move_row(context, change):
    issue_ref = _issue_ref(change['issue_ref'])
    group_id = None if change['group_id'] is None else validate_uuid_text(change['group_id'])
    after = None if change['after_issue_ref'] is None else _issue_ref(change['after_issue_ref'])
    row_order = context['row_order']
    if not row_order['group_order'] and group_id is not None:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if row_order['group_order'] and group_id not in row_order['group_order']:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    rows = [{**row} for row in row_order['rows']]
    moving = next((row for row in rows if _same_issue(row['issue_ref'], issue_ref)), None)
    if moving is None:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    moving['group_id'] = group_id
    remaining = [row for row in rows if not _same_issue(row['issue_ref'], issue_ref)]
    if after is None:
        index = 0
    else:
        match = next((idx for idx, row in enumerate(remaining) if _same_issue(row['issue_ref'], after) and row['group_id'] == group_id), None)
        if match is None:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        index = match + 1
    remaining.insert(index, moving)
    reordered = []
    for position, row in enumerate(remaining, 1):
        reordered.append({**row, 'position': position})
    return {**context, 'row_order': {**row_order, 'revision': row_order['revision'] + 1, 'rows': tuple(reordered)}}


def _authored(value):
    if isinstance(value, AuthoredEdit):
        return value
    return authored_edit_from_mapping(value)


def _change(value):
    if not isinstance(value, Mapping) or type(value.get('kind')) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    fields = {
        **COMMAND_FIELDS,
        'move_row': {'kind', 'issue_ref', 'group_id', 'after_issue_ref'},
        'set_action_tracking': {'kind', 'action_id', 'expected_state', 'state', 'resolution', 'evidence_refs'},
        'add_persistent_note': {'kind', 'note_id', 'target', 'issue_ref', 'fragment', 'carry_forward'},
        'set_persistent_carry': {'kind', 'note_id', 'carry_forward'},
    }.get(value['kind'])
    if fields is None or set(value) != fields:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return dict(value)


def _apply_daily_note(context, request, actor_subject, timestamp):
    note_id = _daily_note_target(request.target)
    observation = next((item for item in context['current_observations'] if item['note_id'] == note_id), None)
    if observation is None:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    notes = list(context['notes'])
    existing_index = next((index for index, note in enumerate(notes) if note['note_id'] == note_id), None)
    existing = None if existing_index is None else notes[existing_index]
    if existing is not None and request.expected_original_hash != existing['body_hash']:
        raise ReportError('REPORT_REVISION_CONFLICT')
    if existing is None and request.expected_original_hash is not None:
        raise ReportError('REPORT_REVISION_CONFLICT')
    fragment = validate_rich_text_fragment(request.fragment)
    body_hash = _fragment_hash(fragment)
    if existing is not None and existing['body_hash'] == body_hash:
        return context
    note = _note_from_observation(observation, existing, fragment, body_hash, actor_subject, timestamp)
    if existing_index is None:
        notes.append(note)
    else:
        notes[existing_index] = note
    return {**context, 'notes': tuple(notes)}


def _apply_continuity_edit(context, request, actor_subject, timestamp):
    scope = request.target.get('scope')
    if scope == 'daily_note':
        return _apply_daily_note(context, request, actor_subject, timestamp)
    if scope == 'persistent_note':
        return _apply_persistent_note_edit(context, request, actor_subject, timestamp)
    if scope == 'report_action':
        return _apply_report_action_edit(context, request, actor_subject, timestamp)
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _apply_persistent_note_edit(context, request, actor_subject, timestamp):
    note_id = validate_uuid_text(request.target.get('note_id'))
    notes = []
    found = False
    for note in context['persistent_notes']:
        if note['note_id'] != note_id:
            notes.append(note)
            continue
        found = True
        notes.append({
            **note,
            'fragment': validate_rich_text_fragment(request.fragment),
            'revision': note['revision'] + 1,
            'provenance': {**note['provenance'], 'origin': 'human', 'edited_by': actor_subject, 'edited_at': timestamp},
        })
    if not found:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {**context, 'persistent_notes': tuple(notes)}


def _apply_report_action_edit(context, request, actor_subject, timestamp):
    action_id = validate_uuid_text(request.target.get('action_id'))
    actions = []
    found = False
    for action in context['actions']:
        if action['action_id'] != action_id:
            actions.append(action)
            continue
        found = True
        actions.append(touch_action({**action, 'body_fragment': validate_rich_text_fragment(request.fragment)},
                                    actor_subject, timestamp))
    if not found:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {**context, 'actions': tuple(actions)}


def _note_from_observation(observation, existing, fragment, body_hash, actor_subject, timestamp):
    return {
        'note_id': observation['note_id'],
        'issue_ref': observation['issue_ref'],
        'meeting': observation['meeting'],
        'revision': 1 if existing is None else existing['revision'] + 1,
        'body_fragment': fragment,
        'body_hash': body_hash,
        'source_status': observation['source_status'],
        'action_ids': () if existing is None else existing['action_ids'],
        'provenance': {
            'origin': 'human',
            'ai_result_ref': None if existing is None else existing['provenance'].get('ai_result_ref'),
            'original_fragment_hash': None if existing is None else existing['body_hash'],
            'edited_by': actor_subject,
            'edited_at': timestamp,
            'accepted_publication': None,
        },
        'prior_revision_hash': None if existing is None else existing['body_hash'],
    }


def _attribute(active_edits, request, actor_subject, timestamp, reference_observations):
    previous = {edit.edit_id: edit for edit in tuple(active_edits or ())}.get(request.edit_id)
    observations = tuple(reference_observations.get(request.edit_id, ()))
    if previous is not None and _same_content(previous, request) and (not observations or previous.reference_observations == observations):
        return previous
    return AuthoredEdit(
        request.edit_id,
        request.kind,
        request.target,
        request.fragment,
        request.expected_original_hash,
        actor_subject,
        timestamp,
        reference_observations=observations,
    )


def _request(value):
    if not isinstance(value, AuthoredEditRequest):
        raise ReportError('REPORT_INVALID')
    reference_receipts = tuple(value.reference_receipts or ())
    if any(type(receipt) is not str for receipt in reference_receipts):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    assist_id = None if value.assist_receipt_id is None else validate_uuid_text(value.assist_receipt_id)
    return AuthoredEditRequest(
        validate_uuid_text(value.edit_id),
        value.kind,
        _mapping(value.target),
        validate_rich_text_fragment(value.fragment),
        None if value.expected_original_hash is None else validate_hash_text(value.expected_original_hash),
        reference_receipts,
        assist_id,
    )


def _daily_note_target(target):
    target = _mapping(target)
    if set(target) != {'scope', 'note_id'} or target['scope'] != 'daily_note':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return validate_uuid_text(target['note_id'])


def _issue_ref(value):
    value = _mapping(value)
    if set(value) != {'provider_id', 'endpoint_fingerprint', 'stable_id', 'key_at_capture'}:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {key: _str(value[key]) for key in value}


def _require_row(context, issue_ref):
    if not any(_same_issue(row['issue_ref'], issue_ref) for row in context['row_order']['rows']):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _same_issue(left, right):
    return (
        left['provider_id'] == right['provider_id']
        and left['endpoint_fingerprint'] == right['endpoint_fingerprint']
        and left['stable_id'] == right['stable_id']
    )


def _bool(value):
    if type(value) is not bool:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _literal(value, allowed):
    if type(value) is not str or value not in allowed:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _str(value):
    if type(value) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _same_content(previous, request):
    return (
        previous.kind == request.kind
        and previous.target == request.target
        and previous.fragment == request.fragment
        and previous.expected_original_hash == request.expected_original_hash
    )


def _fragment_hash(fragment):
    try:
        return sha256_bytes(canonical_bytes(fragment))
    except ArchiveError:
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None


def _mapping(value):
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return dict(value)


def _unique(values):
    items = tuple(values)
    if len(items) != len(set(items)):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
