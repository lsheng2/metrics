import json

from project_management.app.api import reports as report_api
from project_management.reporting.fragment_renderers import rich_fragment_to_html
from project_management.reporting.observations import history_entries, source_observation_label
from project_management.app.domain.report_observation_history import all_observations
from ui_web.report_forms import new_command_id


def pinned_matrix(draft, continuity_edits, *, read_only=False):
    context = draft.authoring_context
    if context is None:
        return None
    projection = report_api.build_meeting_matrix(draft.snapshot, context)
    group_choices = matrix_group_choices(draft)
    notes = {note['note_id']: note for note in context['notes']}
    observations = {item['note_id']: item for item in all_observations(context)}
    actions = {action['action_id']: action for action in context['actions']}
    persistent = {}
    for note in context['persistent_notes']:
        if note['target'] == 'issue':
            persistent.setdefault(target_key(note['issue_ref']), []).append(note)
    rows = []
    projection_rows = list(projection.rows)
    for index, row in enumerate(projection_rows):
        before_previous = projection_rows[index - 2].issue_ref if index > 1 else None
        next_row = projection_rows[index + 1].issue_ref if index + 1 < len(projection_rows) else None
        rows.append(matrix_row(row, notes, observations, actions, persistent, continuity_edits, before_previous, next_row, group_choices, read_only, context))
    return {'columns': projection.columns, 'rows': tuple(rows)}


def matrix_group_choices(draft):
    for block in draft.template_snapshot['resolved_document']['blocks']:
        if block['kind'] == 'data' and block['source'] == 'meeting_matrix':
            groups = tuple(block['options'].get('groups', ()))
            if block['options'].get('group_mode') == 'manual':
                return groups
    return ()


def matrix_row(row, notes, observations, actions, persistent, continuity_edits, before_previous, next_row, group_choices, read_only, context=None):
    return {
        'issue_ref': row.issue_ref,
        'issue_ref_json': json.dumps(row.issue_ref, ensure_ascii=False, separators=(',', ':')),
        'title': row.title,
        'current_key': row.current_key,
        'visibility': row.visibility,
        'workflow_editable': not read_only and bool(context and context['meeting']),
        'persistent_notes': tuple(persistent_note_view(note) for note in persistent.get(target_key(row.issue_ref), ())),
        'group_id': row.group_id or '',
        'group_choices': group_choices,
        'group_move_base': json.dumps({'kind': 'move_row', 'issue_ref': row.issue_ref, 'after_issue_ref': None},
                                      ensure_ascii=False, separators=(',', ':')),
        'move_up_json': json.dumps({
            'kind': 'move_row',
            'issue_ref': row.issue_ref,
            'group_id': row.group_id,
            'after_issue_ref': before_previous,
        }, ensure_ascii=False, separators=(',', ':')),
        'move_down_json': '' if next_row is None else json.dumps({
            'kind': 'move_row',
            'issue_ref': row.issue_ref,
            'group_id': row.group_id,
            'after_issue_ref': next_row,
        }, ensure_ascii=False, separators=(',', ':')),
        'cells': tuple(matrix_cell(cell, notes, observations, actions, continuity_edits, read_only, context, row.issue_ref) for cell in row.cells),
    }


def matrix_cell(cell, notes, observations, actions, continuity_edits, read_only, context=None, issue_ref=None):
    current_day = not read_only and (context is None or bool(context['meeting'] and context['meeting']['local_date'] == cell.local_date))
    readonly_note_ids = tuple(
        note_id for note_id in cell.note_ids
        if note_id in notes and (not current_day or note_id != cell.current_observation_note_id)
    )
    current = None
    if cell.current_observation_note_id and current_day:
        current = daily_note_region(cell.current_observation_note_id, notes, continuity_edits)
    current_prefix = current_observation_prefix(notes, observations, cell.current_observation_note_id)
    has_note = cell.current_observation_note_id in notes
    if not current_day and has_note:
        current_prefix = ''
    entries = None
    if context is not None and issue_ref is not None:
        entries = tuple(
            {'kind': 'note', **readonly_note(item['note'])} if item['kind'] == 'note'
            else {'kind': item['kind'], 'text': item['text']}
            for item in history_entries(context, issue_ref, cell.local_date,
                                        [notes[key] for key in cell.note_ids],
                                        exclude_note_id=cell.current_observation_note_id if current_day else None)
        )
        if not current_day:
            current_prefix = ''
    review = next((item['state'] for item in (context or {}).get('meeting_reviews', ())
                   if item['issue_ref'] == issue_ref and item['meeting']['local_date'] == cell.local_date), 'unreviewed')
    action_ids = list(cell.action_ids)
    if current_day and issue_ref is not None:
        action_ids.extend(key for key, action in actions.items()
                          if key not in action_ids and action['issue_ref'] == issue_ref)
    return {
        'local_date': cell.local_date,
        'state': cell.state,
        'source_state': cell.source_state,
        'display': cell.state,
        'prefix': current_prefix,
        'observation_label': source_observation_label(
            observations.get(cell.current_observation_note_id), has_note=has_note, context=context,
        ) if current_day else '',
        'readonly_entries': entries,
        'review': review,
        'review_editable': current_day and cell.current_observation_note_id is not None and context is not None,
        'review_payload': json.dumps({'kind': 'set_meeting_review', 'issue_ref': issue_ref}, separators=(',', ':')),
        'readonly_notes': tuple(readonly_note(notes[note_id]) for note_id in readonly_note_ids),
        'actions': tuple(action_view(actions[action_id], editable=current_day)
                         for action_id in action_ids if action_id in actions),
        'current_region': current,
    }


def readonly_note(note):
    return {'prefix': source_prefix(note), 'html': rich_fragment_to_html(note['body_fragment'])}


def daily_note_region(note_id, notes, continuity_edits):
    target = {'scope': 'daily_note', 'note_id': note_id}
    current = notes.get(note_id)
    edit = continuity_edits.get(target_key(target))
    payload = {
        'edit_id': edit['edit_id'] if edit else new_command_id(),
        'kind': 'note',
        'target': target,
        'target_json': json.dumps(target, ensure_ascii=False, separators=(',', ':')),
        'fragment': {'schema_version': 2, 'blocks': []} if current is None else current['body_fragment'],
        'expected_original_hash': None if current is None else current['body_hash'],
        'author': edit.get('author', '') if edit else '',
        'edited_at': edit.get('edited_at', '') if edit else '',
        'existing': current is not None,
    }
    script_id = f"report-fragment-{payload['edit_id']}"
    return {**payload, 'fragment_script_id': script_id}


def source_prefix(note):
    meeting = note['meeting']
    status = note['source_status']['value']
    suffix = '' if status is None else f'({status})'
    return f"ww{meeting['workweek']}.{meeting['weekday']}{suffix}:"


def current_observation_prefix(notes, observations, note_id):
    if not note_id:
        return ''
    if note_id in observations:
        observation = observations[note_id]
        meeting = observation['meeting']
        status = observation['source_status']['value']
        suffix = '' if status is None else f'({status})'
        return f"ww{meeting['workweek']}.{meeting['weekday']}{suffix}:"
    if note_id in notes:
        return source_prefix(notes[note_id])
    return ''


def action_view(action, *, editable):
    owner = action['owner_ref'] or {}
    target = {'scope': 'report_action', 'action_id': action['action_id']}
    return {
        'action_id': action['action_id'],
        'label': 'AR' if action['basis'] == 'recorded' else 'AR?',
        'owner': owner.get('display_name') or owner.get('owner_id') or '',
        'state': action['tracking_state'],
        'human': action.get('provenance', {}).get('origin') == 'human',
        'owner_payload': json.dumps({'kind': 'set_action_owner', 'action_id': action['action_id'],
                                     'expected_owner_ref': action['owner_ref']}, separators=(',', ':')),
        'original_owner': owner.get('display_name') or owner.get('owner_id') or '',
        'body_html': rich_fragment_to_html(action['body_fragment']),
        'region': None if not editable else {
            'edit_id': action['action_id'],
            'kind': 'note',
            'target': target,
            'target_json': json.dumps(target, ensure_ascii=False, separators=(',', ':')),
            'fragment': action['body_fragment'],
            'expected_original_hash': '',
            'author': '',
            'edited_at': '',
            'existing': False,
            'fragment_script_id': f"report-fragment-{action['action_id']}",
        },
        'evidence_refs': tuple(action['evidence_refs']),
        'evidence_json': json.dumps(tuple(action['evidence_refs']), ensure_ascii=False, separators=(',', ':')),
    }


def persistent_note_view(note):
    target = {'scope': 'persistent_note', 'note_id': note['note_id']}
    return {
        'note_id': note['note_id'],
        'html': rich_fragment_to_html(note['fragment']),
        'carry_forward': note['carry_forward'],
        'carry_json': json.dumps({
            'kind': 'set_persistent_carry',
            'note_id': note['note_id'],
            'carry_forward': note['carry_forward'],
        }, ensure_ascii=False, separators=(',', ':')),
        'region': {
            'edit_id': note['note_id'],
            'kind': 'note',
            'target': target,
            'target_json': json.dumps(target, ensure_ascii=False, separators=(',', ':')),
            'fragment': note['fragment'],
            'expected_original_hash': '',
            'author': '',
            'edited_at': '',
            'existing': False,
            'fragment_script_id': f"report-fragment-{note['note_id']}",
        },
    }


def target_key(target):
    return tuple(sorted(target.items()))
