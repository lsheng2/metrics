import json

from django.utils.translation import gettext as _

from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text
from project_management.app.api import reports as report_api
from project_management.reporting.fragment_renderers import rich_fragment_to_html
from ui_web.report_continuity_view_model import pinned_matrix
from ui_web.report_forms import new_command_id


def authored_edits_json(draft):
    return json.dumps(tuple(request_edit(edit) for edit in authored_edits(draft)), ensure_ascii=False, separators=(',', ':'))


def authored_edit_rows(draft, target_choices):
    reverse_targets = {tuple(sorted(value.items())): key for key, value in target_choices.target_map.items()}
    labels = dict(target_choices.note_targets + target_choices.override_targets)
    rows = []
    for edit in authored_edits(draft):
        encoded = reverse_targets.get(tuple(sorted(edit['target'].items())))
        if encoded is None:
            continue
        rows.append({
            'edit_id': edit['edit_id'],
            'kind': edit['kind'],
            'target': encoded,
            'target_json': json.dumps(edit['target'], ensure_ascii=False, separators=(',', ':')),
            'target_label': labels.get(encoded, encoded),
            'fragment_json': json.dumps(edit['fragment'], ensure_ascii=False, separators=(',', ':')),
            'expected_original_hash': edit.get('expected_original_hash') or '',
            'author': edit.get('author', ''),
            'edited_at': edit.get('edited_at', ''),
        })
    return tuple(rows)


def report_body(draft, renderer=None):
    if is_pinned_template(draft):
        return pinned_report_body(draft, renderer)
    edits = authored_edits(draft)
    override_by_target = {(edit['kind'], target_key(edit['target'])): edit for edit in edits}
    notes_by_target = {}
    for edit in edits:
        if edit['kind'] == 'note':
            notes_by_target.setdefault(target_key(edit['target']), []).append(edit)
    report_target = {'scope': 'report'}
    return {
        'report_notes': note_regions(report_target, notes_by_target),
        'messages': tuple(message_body(message, override_by_target) for message in draft.snapshot.key_messages),
        'rows': tuple(row_body(row, override_by_target, notes_by_target) for row in draft.snapshot.rows),
    }


def is_pinned_template(draft):
    snapshot = getattr(draft, 'template_snapshot', None)
    return isinstance(snapshot, dict) and report_api.is_pinned_renderer(snapshot.get('renderer_version'))


def pinned_report_body(draft, renderer=None):
    edits = authored_edits(draft)
    slots = {edit['target']['slot_id']: edit for edit in edits if edit['kind'] == 'slot_fill'}
    continuity_edits = {
        target_key(edit['target']): edit
        for edit in edits
        if isinstance(edit.get('target'), dict)
        and edit['target'].get('scope') in {'daily_note', 'persistent_note', 'report_action'}
    }
    blocks = []
    for block in draft.template_snapshot['resolved_document']['blocks']:
        if block['kind'] == 'content':
            blocks.append({
                'kind': 'content',
                'html': rich_fragment_to_html(block['fragment']),
                'text': rich_text_fragment_plain_text(block['fragment']),
            })
        elif block['kind'] == 'slot':
            blocks.append({'kind': 'slot', 'required': block['required'], 'label': block['label'],
                           'slot_id': block['slot_id'],
                           'region': pinned_slot_region(block, slots.get(block['slot_id']))})
        else:
            blocks.append({'kind': 'data', 'source': block['source'], 'label': data_label(block['source']),
                           'html': pinned_data_html(draft, renderer, block),
                           'facts': data_facts(draft, block['source']),
                           'matrix': pinned_matrix(draft, continuity_edits) if block['source'] == 'meeting_matrix' else None})
    return {
        'pinned': True,
        'blocks': tuple(blocks),
        'messages': (),
        'rows': (),
        'report_notes': (),
    }


def pinned_data_html(draft, renderer, block):
    if block['source'] == 'meeting_matrix':
        return ''
    if renderer is None:
        return ''
    authored_edits = tuple(
        edit for edit in draft.authored_edits
        if not (isinstance(edit.target, dict) and edit.target.get('scope') in {'daily_note', 'persistent_note', 'report_action'})
    )
    html, _ = renderer.render_pinned_data_block(
        draft.snapshot,
        draft.template_snapshot,
        authored_edits,
        block,
        draft_id=draft.draft_id,
        revision=draft.revision,
        revision_hash=draft.revision_hash,
        edition_state=draft.state,
    )
    return html


def pinned_slot_region(block, edit):
    target = {'scope': 'template_slot', 'slot_id': block['slot_id']}
    if edit is not None:
        return region(edit, target, True)
    return region({
        'edit_id': new_command_id(),
        'kind': 'slot_fill',
        'target': target,
        'fragment': block['initial'],
        'expected_original_hash': None,
        'author': '',
        'edited_at': '',
    }, target, False)


def data_label(source):
    return {
        'meeting_matrix': _('Meeting matrix'),
        'key_messages': _('Key messages'),
        'changes': _('Changes'),
        'register': _('Issue register'),
        'coverage': _('Coverage'),
        'weekly_timeline': _('Weekly timeline'),
    }.get(source, source)


def data_facts(draft, source):
    if source == 'key_messages':
        return (_('%(count)s key messages') % {'count': len(draft.snapshot.key_messages)},)
    if source == 'changes':
        return (_('%(count)s source changes') % {'count': len(draft.snapshot.events)},)
    if source == 'register':
        return (_('%(count)s issue rows') % {'count': len(draft.snapshot.rows)},)
    if source == 'coverage':
        coverage = draft.snapshot.coverage
        return (_('%(accepted)s accepted, %(pending)s pending') % {
            'accepted': value_from(coverage, 'accepted_count', 0),
            'pending': value_from(coverage, 'pending_count', 0),
        },)
    if source == 'weekly_timeline':
        return (_('%(count)s timeline days') % {'count': len(draft.snapshot.days)},)
    return ()


def value_from(value, name, default):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def target_payloads(snapshot, choices, target_map, *, include_hash):
    payloads = []
    for value, label in choices:
        target = target_map[value]
        original = report_api.original_target_text(snapshot, target)
        payloads.append({
            'value': value,
            'label': label,
            'target_json': json.dumps(target, ensure_ascii=False, separators=(',', ':')),
            'expected_original_hash': report_api.text_hash(original or '') if include_hash else '',
        })
    return tuple(payloads)


def authored_edits(draft):
    if draft.authored_edits:
        return tuple(authored_edit_payload(edit) for edit in draft.authored_edits)
    return tuple({
        'edit_id': edit.edit_id,
        'kind': edit.kind,
        'target': edit.target,
        'fragment': plain_text_fragment_payload(edit.text),
        'expected_original_hash': edit.expected_original_hash,
        'reference_receipts': [],
        'assist_receipt_id': None,
        'author': edit.author,
        'edited_at': edit.edited_at,
    } for edit in draft.edits)


def authored_edit_payload(edit):
    return {
        'edit_id': edit.edit_id,
        'kind': edit.kind,
        'target': edit.target,
        'fragment': edit.fragment,
        'expected_original_hash': edit.expected_original_hash,
        'reference_receipts': [],
        'assist_receipt_id': None,
        'author': edit.author,
        'edited_at': edit.edited_at,
    }


def request_edit(edit):
    return {
        'edit_id': edit['edit_id'],
        'kind': edit['kind'],
        'target': edit['target'],
        'fragment': edit['fragment'],
        'expected_original_hash': edit.get('expected_original_hash'),
        'reference_receipts': [],
        'assist_receipt_id': None,
    }


def message_body(message, overrides):
    target = {'scope': 'message', 'message_id': message.message_id, 'field': 'text'}
    return {
        'message_id': message.message_id,
        'source_refs': message.source_refs,
        'text_region': narrative_region(target, message.text, overrides),
    }


def row_body(row, overrides, notes):
    key_hash = report_api.source_key_hash(row.source_key)
    issue_target = {'scope': 'issue', 'source_key_hash': key_hash}
    return {
        'key': row.identity.display_key,
        'title': row.title or '',
        'status': row.status or '',
        'assignee': assignee_label(row.assignee),
        'source_refs': tuple(item.get('ref_id', '') for item in row.evidence),
        'what_region': narrative_region(dict(issue_target, field='what'), row.what or '', overrides),
        'position_region': narrative_region(dict(issue_target, field='current_position'), row.current_position or '', overrides),
        'verification_region': narrative_region(dict(issue_target, field='verification'), row.verification or '', overrides),
        'note_regions': note_regions(issue_target, notes),
        'actions': action_bodies(row, key_hash, notes, overrides),
    }


def action_bodies(row, key_hash, notes, overrides):
    actions = []
    for index, action in enumerate(row.next_actions):
        target = {
            'scope': 'action',
            'source_key_hash': key_hash,
            'summary_id': row.summary_ref.summary_id,
            'action_index': index,
        }
        actions.append({
            'label': action.get('action') or _('Action %(number)s') % {'number': index + 1},
            'action_region': narrative_region(dict(target, field='action'), str(action.get('action') or ''), overrides),
            'owner_region': narrative_region(dict(target, field='owner_display'), owner_display(action), overrides),
            'note_regions': note_regions(target, notes),
        })
    return tuple(actions)


def narrative_region(target, original, overrides):
    edit = overrides.get(('narrative_override', target_key(target)))
    if edit is not None:
        return region(edit, target, True)
    return region({
        'edit_id': new_command_id(),
        'kind': 'narrative_override',
        'target': target,
        'fragment': plain_text_fragment_payload(original),
        'expected_original_hash': report_api.text_hash(original),
        'author': '',
        'edited_at': '',
    }, target, False)


def note_regions(target, notes):
    regions = [region(edit, target, True) for edit in notes.get(target_key(target), ())]
    regions.append(region({
        'edit_id': new_command_id(),
        'kind': 'note',
        'target': target,
        'fragment': {'schema_version': 2, 'blocks': []},
        'expected_original_hash': None,
        'author': '',
        'edited_at': '',
    }, target, False))
    return tuple(regions)


def region(edit, target, existing):
    script_id = f"report-fragment-{edit['edit_id']}"
    return {
        'edit_id': edit['edit_id'],
        'kind': edit['kind'],
        'target': target,
        'target_json': json.dumps(target, ensure_ascii=False, separators=(',', ':')),
        'expected_original_hash': edit.get('expected_original_hash') or '',
        'fragment': edit['fragment'],
        'fragment_script_id': script_id,
        'existing': existing,
        'author': edit.get('author', ''),
        'edited_at': edit.get('edited_at', ''),
    }


def target_key(target):
    return tuple(sorted(target.items()))


def assignee_label(assignee):
    if isinstance(assignee, dict):
        return assignee.get('displayName') or assignee.get('key') or ''
    return str(assignee or '')


def owner_display(action):
    for field in ('owner_display', 'ownerDisplay', 'displayName', 'owner_id'):
        value = action.get(field)
        if type(value) is str and value:
            return value
    return ''


def plain_text_fragment_payload(value):
    if value == '':
        return {'schema_version': 2, 'blocks': []}
    return {
        'schema_version': 2,
        'blocks': [{'type': 'paragraph', 'content': [{
            'type': 'text', 'text': value, 'marks': [], 'foreground': None, 'background': None,
        }]}],
    }
