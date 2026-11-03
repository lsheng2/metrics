def build_plain_text(model) -> str:
    lines = [
        model['title'],
        f"Project: {model['metadata']['project_name']} / {model['metadata']['stage_name']}",
        f"Report date: {model['metadata']['report_date']}",
        f"Source cutoff: {model['metadata']['source_as_of']} {model['metadata']['timezone']}",
        f"Edition: {model['metadata']['edition_state']} draft {model['metadata']['draft_id']} rev {model['metadata']['revision']}",
        f"Revision hash: {model['metadata']['revision_hash']}" if model['metadata']['revision_hash'] else "Revision hash: unbound",
        f"Baseline: {model['metadata']['baseline']}",
        f"Capture id: {model['metadata']['capture_id']}",
        f"Source commit: {model['metadata']['source_commit']}",
        f"Rule hash: {model['metadata']['rule_hash']}",
        f"Comparison policy: {model['metadata']['comparison_policy_hash']}",
        f"Template hash: {model['metadata']['template_hash']}",
        f"Renderer version: {model['metadata']['renderer_version']}",
        '',
    ]
    if model.get('timeline'):
        _append_timeline(lines, model['timeline'])
    for section in model['sections']:
        if section == 'key_messages':
            _append_messages(lines, model['key_messages'])
        if section == 'changes':
            _append_events(lines, model['events'])
        if section == 'register':
            _append_rows(lines, model['groups'])
        if section == 'coverage':
            _append_coverage(lines, model)
    return '\n'.join(lines)


def _append_messages(lines, messages):
    lines.append('Key messages')
    for message in messages:
        lines.append(f"- {message['message_id']}: {message['text']['text']} ({message['source_refs']})")
        _append_edit(lines, message['text'])
    lines.append('')


def _append_events(lines, events):
    lines.append('Changes')
    for event in events:
        lines.append(
            f"- {event['event_id']} {event['kind']} before {event['before']} after {event['after']} "
            f"Occurred: {event['occurred_at']} Observed: {event['observed_at']} refs {event['source_refs']}"
        )
    lines.append('')


def _append_rows(lines, groups):
    lines.append('Issue register')
    for group in groups:
        lines.append(f"Group: {group['label']}")
        for row in group['rows']:
            lines.extend(_row_lines(row))
    lines.append('')


def _row_lines(row):
    lines = [
        f"[{row['display_key']}] {row['title']}",
        f"Status: {row['status']}; Assignee: {row['assignee']}; Source: {row['source_url_text']}",
        f"Source hash: {row['source_hash']}; Summary: {row['summary_id']} r{row['summary_revision']}",
        f"What: {row['what']['text']}",
        f"Current position: {row['current_position']['text']}",
        f"Verification: {row['verification']['text']}",
        f"Pending reason: {row['pending_reason']}; Summary as of: {row['summary_as_of']}",
    ]
    for field in (row['what'], row['current_position'], row['verification']):
        _append_edit(lines, field)
    for action in row['actions']:
        lines.append(
            f"Action {action['index']}: {action['action']['text']}; Owner: {action['owner_display']['text']}; "
            f"Basis: {action['owner_basis']}; Action state: {action['state']}; quote: {action['owner_quote']}; "
            f"evidence: {action['evidence_refs']}; source confirmed: {action['owner_confirmed']}"
        )
        if action['owner_display']['edited']:
            lines.append(f"Human proposal; source confirmed: {action['owner_confirmed']}")
        _append_edit(lines, action['action'])
        _append_edit(lines, action['owner_display'])
        for note in action['notes']:
            lines.append(f"Meeting note: {note['text']} ({note['provenance']})")
    for note in row['notes']:
        lines.append(f"Meeting note: {note['text']} ({note['provenance']})")
    return lines


def _append_coverage(lines, model):
    lines.append('Evidence and coverage')
    for item in model['coverage_items']:
        lines.append(f"{item['label']}: {item['value']}")
    for group in model['evidence_groups']:
        for evidence in group['evidence']:
            lines.append(
                f"{group['display_key']} issue source hash {group['source_hash']} "
                f"{evidence['ref_id']} capture {evidence['capture_id']} "
                f"pointer {evidence['pointer']} evidence source hash {evidence['source_hash']} "
                f"value {evidence['value']}"
            )
    for note in model['report_notes']:
        lines.append(f"Meeting note: {note['text']} ({note['provenance']})")
    lines.append('')


def _append_timeline(lines, timeline):
    lines.append('Weekly timeline')
    for day in timeline['days']:
        lines.append(f"{day['report_date']}: {day['state']} publication {day['publication_id']}")
    for row in timeline['rows']:
        lines.append(f"{row['display_key']}: " + ' | '.join(cell['text'] for cell in row['cells']))
    for event in timeline['day_events']:
        lines.append(
            f"{event['report_date']} {event['identity']} {event['event_id']} {event['kind']} "
            f"before {event['before']} after {event['after']} occurred {event['occurred_at']} "
            f"observed {event['observed_at']}"
        )
    lines.append('')


def _append_edit(lines, field):
    if field['edited']:
        lines.append(f"{field['provenance']}; Original: {field['original']}")
