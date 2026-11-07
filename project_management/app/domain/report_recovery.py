from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.report_authoring import AuthoredEdit, AuthoredEditRequest, validate_authored_edit_requests
from project_management.app.domain.report_authoring_fragments import validate_rich_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_continuity_edits import _change, _request, validate_continuity_authored_edits
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_observation_history import issue_key


RECOVERY_LIMIT = 1_048_576
EDIT_KEYS = {'edit_id', 'kind', 'target', 'fragment', 'expected_original_hash', 'reference_receipts', 'assist_receipt_id'}
REQUEST_KEYS = {'client_id', 'sequence', 'base_revision', 'base_revision_hash', 'snapshot_hash', 'template_hash', 'content'}


def validate_recovery_request(value, draft):
    if not isinstance(value, Mapping) or set(value) != REQUEST_KEYS:
        raise ReportError('REPORT_INVALID')
    validate_uuid_text(value['client_id'])
    for name in ('sequence', 'base_revision'):
        if type(value[name]) is not int or not 1 <= value[name] <= 1_000_000:
            raise ReportError('REPORT_INVALID')
    for name in ('base_revision_hash', 'snapshot_hash', 'template_hash'):
        validate_hash_text(value[name])
    if (value['base_revision'] != draft.revision or value['base_revision_hash'] != draft.revision_hash
            or value['snapshot_hash'] != draft.snapshot_hash
            or value['template_hash'] != draft.template_definition.template_hash):
        raise ReportError('REPORT_REVISION_CONFLICT')
    content = value['content']
    if not isinstance(content, Mapping) or set(content) != {'edits', 'continuity_changes', 'save_request'}:
        raise ReportError('REPORT_INVALID')
    if len(canonical_bytes(value)) > RECOVERY_LIMIT:
        raise ReportError('REPORT_LIMIT')
    _validate_content(content, draft)
    pending = content['save_request']
    if pending is not None:
        if not isinstance(pending, Mapping) or set(pending) != {
                'command_id', 'expected_revision', 'expected_revision_hash', 'edits', 'continuity_changes'}:
            raise ReportError('REPORT_INVALID')
        validate_uuid_text(pending['command_id'])
        if (pending['expected_revision'] != draft.revision
                or pending['expected_revision_hash'] != draft.revision_hash):
            raise ReportError('REPORT_REVISION_CONFLICT')
        _validate_content(pending, draft)
    return decode_json(canonical_bytes(value))


def _validate_content(content, draft):
    values, changes = content['edits'], content['continuity_changes']
    if not isinstance(values, (list, tuple)) or len(values) > 100 or not isinstance(changes, (list, tuple)) or len(changes) > 100:
        raise ReportError('REPORT_LIMIT')
    requests = []
    for item in values:
        if not isinstance(item, Mapping) or set(item) != EDIT_KEYS:
            raise ReportError('REPORT_INVALID')
        requests.append(_request(AuthoredEditRequest(**item)))
    if len({item.edit_id for item in requests}) != len(requests):
        raise ReportError('REPORT_INVALID')
    continuity = tuple(item for item in requests if item.target.get('scope') in {'daily_note', 'persistent_note', 'report_action'})
    standard = tuple(item for item in requests if item not in continuity)
    validate_authored_edit_requests(draft.snapshot, standard, draft.template_snapshot)
    if continuity:
        if draft.authoring_context is None:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        validate_continuity_authored_edits(draft.authoring_context, tuple(
            AuthoredEdit(item.edit_id, item.kind, item.target, item.fragment,
                         item.expected_original_hash, 'recovery', draft.updated_at) for item in continuity
        ))
    if changes and (draft.authoring_context is None or draft.authoring_context['report_role'] != 'daily'):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    for item in changes:
        _validate_change(_change(item), draft.authoring_context)


def _validate_change(change, context):
    rows = {issue_key(row['issue_ref']) for row in context['row_order']['rows']}
    for field in ('issue_ref', 'after_issue_ref'):
        if change.get(field) is not None:
            try:
                if issue_key(change[field]) not in rows:
                    raise ReportError('REPORT_EDIT_TARGET_INVALID')
            except (KeyError, TypeError):
                raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    for field in ('fragment', 'resolution'):
        if field in change:
            validate_rich_text_fragment(change[field])
    for field in ('action_id', 'note_id'):
        if field in change:
            validate_uuid_text(change[field])
    if change['kind'] == 'set_meeting_review' and (type(change['state']) is not str or change['state'] not in {
            'unreviewed', 'discussed', 'not_discussed', 'no_additional_update'}):
        raise ReportError('REPORT_INVALID')
    if change['kind'] == 'set_action_tracking':
        if any(type(change[field]) is not str or change[field] not in {'open', 'done', 'canceled', 'unknown'}
               for field in ('expected_state', 'state')):
            raise ReportError('REPORT_INVALID')
        if not isinstance(change['evidence_refs'], (list, tuple)) or any(type(item) is not str for item in change['evidence_refs']):
            raise ReportError('REPORT_INVALID')
    if change['kind'] in {'set_persistent_carry', 'add_persistent_note'} and type(change['carry_forward']) is not bool:
        raise ReportError('REPORT_INVALID')
    if change['kind'] == 'add_persistent_note':
        if (type(change['target']) is not str or change['target'] not in {'report', 'issue'}
                or (change['target'] == 'report') != (change['issue_ref'] is None)):
            raise ReportError('REPORT_INVALID')
    if change['kind'] in {'set_action_tracking', 'set_action_owner'}:
        if not any(item['action_id'] == change['action_id'] for item in context['actions']):
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if change['kind'] == 'set_persistent_carry':
        if not any(item['note_id'] == change['note_id'] for item in context['persistent_notes']):
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    for field in ('owner_ref', 'expected_owner_ref'):
        value = change.get(field)
        if value is not None:
            if not isinstance(value, Mapping) or set(value) != {'owner_id', 'display_name'} or any(
                    type(item) is not str or len(item) > 160 for item in value.values()):
                raise ReportError('REPORT_INVALID')
