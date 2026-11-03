import json
from typing import Mapping

from project_management.app.domain.capture_values import json_value
from project_management.app.domain.report_contracts import ReportSourceSnapshot
from project_management.app.domain.report_edits import source_key_hash
from project_management.reporting.timeline import build_timeline, validate_days
from project_management.reporting.validation import require_safe_https_url


def build_report_model(
    snapshot: ReportSourceSnapshot,
    template_definition,
    edits,
    *,
    draft_id: str,
    revision: int,
    revision_hash: str | None,
    edition_state: str,
) -> dict:
    validate_days(snapshot)
    edit_state = _edit_state(edits)
    rows = [_row_model(row, edit_state) for row in sorted(snapshot.rows, key=_row_sort_key)]
    return {
        'title': _title(template_definition.template_id),
        'template_id': template_definition.template_id,
        'sections': template_definition.options['section_order'],
        'optional_columns': template_definition.options['optional_columns'],
        'metadata': _metadata(snapshot, template_definition, draft_id, revision, revision_hash, edition_state),
        'key_messages': _messages(snapshot, edit_state),
        'events': [_event_model(event) for event in snapshot.events],
        'groups': _groups(rows, template_definition.options['group_by']),
        'rows': rows,
        'coverage_items': _coverage_items(snapshot.coverage),
        'evidence_groups': _evidence_groups(rows),
        'report_notes': edit_state['report_notes'],
        'timeline': build_timeline(snapshot, rows) if template_definition.template_id == 'weekly-timeline' else None,
    }


def _metadata(snapshot, template_definition, draft_id, revision, revision_hash, edition_state):
    baseline = snapshot.baseline_publication_id or 'initial_baseline/no-published-history'
    return {
        'project_name': snapshot.project_name,
        'stage_name': snapshot.stage_name,
        'owner_subject': snapshot.owner_subject,
        'report_date': snapshot.report_date,
        'source_as_of': snapshot.source_as_of,
        'timezone': snapshot.timezone,
        'baseline': baseline,
        'edition_state': edition_state,
        'draft_id': draft_id,
        'revision': revision,
        'revision_hash': revision_hash,
        'capture_id': snapshot.capture_id,
        'source_commit': snapshot.source_commit,
        'rule_hash': snapshot.rule_hash,
        'comparison_policy_hash': snapshot.comparison_policy_hash,
        'template_hash': template_definition.template_hash,
        'renderer_version': template_definition.renderer_version,
    }


def _messages(snapshot, edit_state):
    result = []
    for message in snapshot.key_messages:
        key = ('message', message.message_id, 'text')
        result.append({
            'message_id': message.message_id,
            'text': _value_with_override(message.text, edit_state['overrides'].get(key)),
            'source_refs': ', '.join(message.source_refs) or 'None',
        })
    return result


def _row_model(row, edit_state):
    row_hash = source_key_hash(row.source_key)
    return {
        'source_key_hash': row_hash,
        'display_key': row.identity.display_key,
        'provider_id': row.identity.provider_id,
        'stable_id': row.identity.stable_id,
        'title': _display(row.title),
        'status': _display(row.status),
        'assignee': _display(row.assignee),
        'source_url_href': _source_url(row.source_url),
        'source_url_text': row.source_url or 'No source link',
        'source_hash': row.source_hash or 'Unknown',
        'coverage_items': _coverage_items(row.coverage),
        'summary_id': row.summary_ref.summary_id if row.summary_ref else 'No summary',
        'summary_revision': row.summary_ref.revision if row.summary_ref else 'Unknown',
        'summary_as_of': row.summary_as_of or 'Unknown',
        'pending_reason': row.pending_reason or 'None',
        'what': _row_field(row_hash, 'what', row.what, edit_state),
        'current_position': _row_field(row_hash, 'current_position', row.current_position, edit_state),
        'verification': _row_field(row_hash, 'verification', row.verification, edit_state),
        'actions': _actions(row, row_hash, edit_state),
        'notes': edit_state['issue_notes'].get(row_hash, ()),
        'evidence': [_evidence(item) for item in row.evidence],
        'blocker_refs': ', '.join(row.blocker_refs) or 'None',
        'limitation_refs': ', '.join(row.limitation_refs) or 'None',
    }


def _actions(row, row_hash, edit_state):
    actions = []
    summary_id = row.summary_ref.summary_id if row.summary_ref else ''
    for index, action in enumerate(row.next_actions):
        action_key = ('action', row_hash, summary_id, index, 'action')
        owner_key = ('action', row_hash, summary_id, index, 'owner_display')
        note_key = ('action', row_hash, summary_id, index)
        actions.append({
            'index': index,
            'action': _value_with_override(_string_or_empty(action.get('action')), edit_state['overrides'].get(action_key)),
            'owner_display': _value_with_override(
                _owner_display(action),
                edit_state['overrides'].get(owner_key),
                human_owner=True,
            ),
            'owner_id': _display(action.get('owner_id')),
            'owner_basis': _display(action.get('owner_basis')),
            'owner_quote': _display(action.get('owner_quote'), 'None'),
            'owner_confirmed': str(bool(action.get('owner_confirmed'))).lower(),
            'state': _display(action.get('state'), 'unknown'),
            'evidence_refs': ', '.join(str(item) for item in action.get('evidence', ())) or 'None',
            'notes': edit_state['action_notes'].get(note_key, ()),
        })
    return actions


def _row_field(row_hash, field, value, edit_state):
    key = ('issue', row_hash, field)
    return _value_with_override(_string_or_empty(value), edit_state['overrides'].get(key))


def _value_with_override(original: str, edit, *, human_owner: bool = False):
    if edit is None:
        return {
            'text': original or 'Unavailable',
            'edited': False,
            'original': '',
            'provenance': '',
            'human_owner': False,
        }
    return {
        'text': edit.text,
        'edited': True,
        'original': original,
        'provenance': _provenance(edit),
        'human_owner': human_owner,
    }


def _edit_state(edits):
    state = {'report_notes': [], 'issue_notes': {}, 'action_notes': {}, 'overrides': {}}
    for edit in edits:
        target = edit.target
        scope = target['scope']
        if edit.kind == 'note':
            _add_note(state, scope, target, edit)
        else:
            state['overrides'][_override_key(target)] = edit
    return state


def _add_note(state, scope, target, edit):
    note = {'text': edit.text, 'provenance': _provenance(edit)}
    if scope == 'report':
        state['report_notes'].append(note)
    if scope == 'issue':
        state['issue_notes'].setdefault(target['source_key_hash'], []).append(note)
    if scope == 'action':
        key = (target['source_key_hash'], target['summary_id'], target['action_index'])
        state['action_notes'].setdefault(key, []).append(note)


def _override_key(target):
    if target['scope'] == 'issue':
        return ('issue', target['source_key_hash'], target['field'])
    if target['scope'] == 'action':
        return (
            'action',
            target['source_key_hash'],
            target['summary_id'],
            target['action_index'],
            target['field'],
        )
    return ('message', target['message_id'], target['field'])


def _groups(rows, group_by):
    if group_by == 'none':
        return [{'label': 'All work items', 'rows': rows}]
    grouped = {}
    for row in rows:
        label = row[group_by] if row[group_by] else 'Unknown'
        grouped.setdefault(label, []).append(row)
    return [{'label': label, 'rows': grouped[label]} for label in sorted(grouped.keys())]


def _event_model(event):
    return {
        'event_id': event.event_id,
        'display_key': event.source_key.stable_id,
        'kind': event.kind,
        'before': _json_text(event.before),
        'after': _json_text(event.after),
        'occurred_at': event.occurred_at or 'unknown',
        'observed_at': event.observed_at,
        'source_refs': ', '.join(event.source_refs) or 'None',
    }


def _evidence_groups(rows):
    return [
        {'display_key': row['display_key'], 'source_hash': row['source_hash'], 'evidence': row['evidence']}
        for row in rows
    ]


def _evidence(item):
    return {
        'ref_id': _display(item.get('ref_id')),
        'capture_id': _display(item.get('capture_id')),
        'pointer': _display(item.get('json_pointer') if item.get('json_pointer') is not None else item.get('pointer')),
        'source_hash': _display(item.get('source_hash')),
        'value': _literal_value(item.get('value')),
    }


def _coverage_items(value, prefix=''):
    if not isinstance(value, Mapping):
        return [{'label': prefix or 'coverage', 'value': _display(value)}]
    items = []
    for key in sorted(value.keys()):
        current = value[key]
        label = f'{prefix}.{key}' if prefix else key
        if isinstance(current, Mapping) and 'state' in current:
            items.append({'label': label, 'value': _display(current['state'])})
            for child_key in sorted(set(current.keys()) - {'state'}):
                items.extend(_coverage_items({child_key: current[child_key]}, label))
        elif isinstance(current, Mapping):
            items.extend(_coverage_items(current, label))
        else:
            items.append({'label': label, 'value': _display(current)})
    return items


def _coverage_summary(value):
    if not isinstance(value, Mapping):
        return _display(value)
    return ';'.join(f"{item['label']}={item['value']}" for item in _coverage_items(value))


def _source_url(value):
    if value is None:
        return None
    return require_safe_https_url(value)


def _display(value, unknown='Unknown') -> str:
    if value is None or value == '':
        return unknown
    if isinstance(value, Mapping):
        for key in ('displayName', 'display_name', 'name', 'display', 'id', 'key'):
            if value.get(key):
                return str(value[key])
        return _json_text(value)
    if isinstance(value, (tuple, list)):
        return ', '.join(_display(item, unknown) for item in value)
    return str(value)


def _json_text(value) -> str:
    if value is None:
        return 'None'
    return json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _literal_value(value) -> str:
    if value is None:
        return 'None'
    if isinstance(value, (Mapping, tuple, list)):
        return _json_text(value)
    return str(value)


def _string_or_empty(value) -> str:
    return '' if value is None else str(value)


def _row_sort_key(row):
    return (row.identity.display_key, row.identity.provider_id, row.identity.stable_id)


def _title(template_id):
    return 'Weekly timeline' if template_id == 'weekly-timeline' else 'Daily standup report'


def _provenance(edit):
    if edit.author and edit.edited_at:
        return f'Edited by {edit.author} at {edit.edited_at}'
    if edit.author:
        return f'Edited by {edit.author}'
    return 'Edited'


def _owner_display(action: Mapping) -> str:
    for field in ('owner_display', 'ownerDisplay', 'displayName', 'owner_id'):
        value = action.get(field)
        if type(value) is str and value:
            return value
    return ''
