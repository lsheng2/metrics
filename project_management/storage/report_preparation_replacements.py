from project_management.app.domain.report_contracts import ReportError


def slot_supersedes_intent(store, slot, intent):
    return (
        slot is not None
        and slot.get('schema_version') == 2
        and slot['slot_id'] == intent['slot_id']
        and slot['slot_key'] == intent['slot_key']
        and slot['superseded_preparation_id'] == intent['preparation_id']
        and slot['superseded_intent_hash'] == store._hash(intent)
    )


def slot_allows_replay(store, slot, intent):
    if slot is None:
        return False
    if (slot['preparation_id'] == intent['preparation_id']
            and slot['slot_id'] == intent['slot_id']
            and slot['slot_key'] == intent['slot_key']
            and slot['intent_hash'] == store._hash(intent)):
        return True
    return slot_has_ancestor(store, slot, intent)


def slot_has_ancestor(store, slot, intent):
    current = store.intent(slot['preparation_id'])
    if slot['intent_hash'] != store._hash(current):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    seen = set()
    for _ in range(16):
        if current['preparation_id'] in seen:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        seen.add(current['preparation_id'])
        if (current['preparation_id'] == intent['preparation_id']
                and store._hash(current) == store._hash(intent)
                and current['slot_id'] == intent['slot_id']):
            return True
        if current.get('schema_version') != 3:
            return False
        parent = store.intent(current['parent_preparation_id'])
        if current['parent_intent_hash'] != store._hash(parent) or parent['slot_id'] != intent['slot_id']:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        current = parent
    raise ReportError('REPORT_ARTIFACT_INVALID')


def verify_replacement_adoption(store, command_id, request_hash, previous, adopted, replacement):
    if adopted['command_id'] != command_id or adopted['request_hash'] != request_hash:
        raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')
    immutable = (
        'preparation_id', 'slot_id', 'slot_key', 'project_id', 'stage_id',
        'owner_subject', 'series_id', 'series_policy_hash', 'meeting_date',
        'parent_preparation_id', 'parent_intent_hash', 'parent_operation_id',
        'expected_parent_operation_revision', 'expected_parent_operation_state',
        'parent_draft_id', 'expected_parent_draft_revision',
        'expected_parent_draft_revision_hash', 'operation_command_id',
        'derived_operation_id', 'operation_id', 'draft_command_id', 'draft_id',
    )
    if any(adopted[key] != replacement[key] for key in immutable):
        raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')
    if adopted['parent_preparation_id'] != previous['preparation_id'] or adopted['parent_intent_hash'] != store._hash(previous):
        raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')


def has_replacement_descendant(store, intent):
    root = store.runtime / 'report-preparations'
    if not root.exists():
        return False
    for path in sorted(root.glob('*/intent.json')):
        candidate = store._read_intent(path.parent.name)
        if candidate.get('schema_version') != 3 or candidate.get('slot_id') != intent['slot_id']:
            continue
        current = candidate
        for _ in range(16):
            if current.get('schema_version') != 3:
                break
            if current['parent_preparation_id'] == intent['preparation_id'] and current['parent_intent_hash'] == store._hash(intent):
                return True
            current = store.intent(current['parent_preparation_id'])
    return False
