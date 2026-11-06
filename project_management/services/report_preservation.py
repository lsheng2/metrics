from dataclasses import dataclass, replace
from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring import AuthoredEdit, authored_edit_from_mapping
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_draft_values import canonical_hash
from project_management.app.domain.report_publication_contracts import publication_path
from project_management.services.report_publication_reads import ReportPublicationReader
from project_management.storage.report_drafts import ReportDraftStore


@dataclass(frozen=True, slots=True)
class PreservedSeedContent:
    context: Mapping
    preservation: Mapping | None


def reprepare_parent_draft(draft_service, actor, project_id, stage_id, intent):
    if intent.get('kind') != 'daily_reprepare' or intent.get('parent_draft_id') is None:
        return None
    with draft_service.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
        draft = ReportDraftStore(
            repository, draft_service.archive.config.root,
            draft_service.archive.config.limits, draft_service.limits,
        ).read_draft(intent['parent_draft_id'], revision=intent['expected_parent_draft_revision'])
    if draft.revision_hash != intent['expected_parent_draft_revision_hash']:
        raise ReportError('REPORT_REVISION_CONFLICT')
    return draft


def preserve_parent_content(parent_draft, context, template_snapshot, historical_resolver=None):
    if parent_draft is None:
        return PreservedSeedContent(context, None)
    if parent_draft.authoring_context is None:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    merged, context_review_issues = _merge_context(parent_draft.authoring_context, context)
    review_issues = list(context_review_issues)
    initial_edits = []
    for edit in parent_draft.authored_edits:
        available, issue = _edit_target_availability(edit, merged, template_snapshot)
        if available:
            initial_edits.append(_historical_reference_edit(edit, parent_draft, historical_resolver))
        elif issue is not None:
            review_issues.append(issue)
    initial_edits = tuple(initial_edits)
    edit_hash = _hash(initial_edits)
    preservation = {
        'schema_version': 1,
        'source_kind': 'parent_draft_revision',
        'parent_draft_id': parent_draft.draft_id,
        'parent_draft_revision': parent_draft.revision,
        'parent_draft_revision_hash': parent_draft.revision_hash,
        'initial_authored_edits': initial_edits,
        'initial_authored_edits_hash': edit_hash,
        'review_issues': tuple(review_issues),
    }
    preservation = {**preservation, 'preservation_hash': _hash({
        key: value for key, value in preservation.items() if key != 'initial_authored_edits'
    })}
    return PreservedSeedContent(merged, _plain_json(preservation))


def preserve_publication_content(repository, publication_ref, context, template_snapshot):
    if publication_ref is None:
        return PreservedSeedContent(context, None)
    publication = ReportPublicationReader(repository).get(publication_ref.publication_id, repository.owner_subject)
    if publication.manifest_sha256 != publication_ref.manifest_hash or publication.commit_id != publication_ref.commit:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    edits_payload = decode_json(repository.read_file(publication_path(publication.manifest.publication_id, 'edits.json'), publication.commit_id))
    source_context = _selected_publication_context(edits_payload)
    initial_edits = []
    review_issues = []
    for edit in _selected_publication_edits(edits_payload):
        if _source_publication_edit_is_historical_only(edit, source_context, context):
            continue
        available, issue = _edit_target_availability(edit, context, template_snapshot)
        if available:
            initial_edits.append(_publication_reference_edit(edit, publication))
        elif issue is not None:
            review_issues.append(issue)
    initial_edits = tuple(initial_edits)
    preservation = {
        'schema_version': 1,
        'source_kind': 'source_publication',
        'publication_id': publication.manifest.publication_id,
        'manifest_hash': publication.manifest_sha256,
        'commit': publication.commit_id,
        'initial_authored_edits': initial_edits,
        'initial_authored_edits_hash': _hash(initial_edits),
        'review_issues': tuple(review_issues),
    }
    preservation = {**preservation, 'preservation_hash': _hash({
        key: value for key, value in preservation.items() if key != 'initial_authored_edits'
    })}
    return PreservedSeedContent(context, _plain_json(preservation))


def _merge_context(parent, current):
    parent = validate_daily_authoring_context(parent)
    current = validate_daily_authoring_context(current)
    rows = current['row_order']['rows']
    issue_keys = {_issue_key(row['issue_ref']) for row in rows}
    observations = {item['note_id']: item for item in current['current_observations']}
    issues = []
    notes = _merge_notes(parent, current, observations)
    actions, action_issues = _merge_actions(parent, current, issue_keys)
    persistent, persistent_issues = _merge_persistent(parent, current, issue_keys)
    row_order, row_issues = _merge_row_order(parent['row_order'], current['row_order'])
    issues.extend(action_issues)
    issues.extend(persistent_issues)
    issues.extend(row_issues)
    merged = {
        **current,
        'row_order': row_order,
        'notes': notes,
        'actions': actions,
        'persistent_notes': persistent,
    }
    merged = _recompute_weekly_seed(merged)
    return validate_daily_authoring_context(merged), tuple(issues)


def _merge_notes(parent, current, observations):
    result = {note['note_id']: note for note in current['notes']}
    for note in parent['notes']:
        observation = observations.get(note['note_id'])
        if observation is None:
            continue
        if _human_note(note) or _same_source_note(note, observation):
            result[note['note_id']] = {**note, 'source_status': observation['source_status']}
    return tuple(result.values())


def _merge_actions(parent, current, issue_keys):
    result = {action['action_id']: action for action in current['actions']}
    issues = []
    for action in parent['actions']:
        if _issue_key(action['issue_ref']) not in issue_keys:
            issues.append(_review_issue('report_action_missing', {'scope': 'report_action', 'action_id': action['action_id']},
                                        'Parent action issue is not present in the replacement source.'))
            continue
        result[action['action_id']] = action
    return tuple(result.values()), tuple(issues)


def _merge_persistent(parent, current, issue_keys):
    result = {note['note_id']: note for note in current['persistent_notes']}
    issues = []
    for note in parent['persistent_notes']:
        if note['target'] == 'report' or _issue_key(note['issue_ref']) in issue_keys:
            result[note['note_id']] = note
        else:
            issues.append(_review_issue('persistent_note_missing', {'scope': 'persistent_note', 'note_id': note['note_id']},
                                        'Parent persistent note issue is not present in the replacement source.'))
    return tuple(result.values()), tuple(issues)


def _merge_row_order(parent, current):
    group_order = current['group_order']
    current_by_key = {_issue_key(row['issue_ref']): row for row in current['rows']}
    ordered = []
    used = set()
    issues = []
    for row in sorted(parent['rows'], key=lambda item: item['position']):
        key = _issue_key(row['issue_ref'])
        if key not in current_by_key:
            continue
        if row['group_id'] in group_order or row['group_id'] is None:
            group_id = row['group_id']
        else:
            group_id = current_by_key[key]['group_id']
            issues.append(_review_issue('row_group_removed', {'scope': 'row_order', 'issue_ref': row['issue_ref']},
                                        'Parent row group is not present in the replacement template.'))
        ordered.append({**current_by_key[key], 'group_id': group_id})
        used.add(key)
    for row in sorted(current['rows'], key=lambda item: item['position']):
        key = _issue_key(row['issue_ref'])
        if key not in used:
            ordered.append(row)
    row_order = {**current, 'revision': parent['revision'], 'rows': tuple({**row, 'position': index} for index, row in enumerate(ordered, 1))}
    return row_order, tuple(issues)


def _edit_target_availability(edit, context, template_snapshot):
    target = edit.target
    scope = target.get('scope') if isinstance(target, Mapping) else None
    if scope == 'daily_note':
        available = any(item['note_id'] == target.get('note_id') for item in context['current_observations'])
        issue = None if available else _review_issue('daily_note_missing', target, 'Parent daily note target is not present in the replacement context.')
        return available, issue
    if scope == 'persistent_note':
        available = any(item['note_id'] == target.get('note_id') for item in context['persistent_notes'])
        issue = None if available else _review_issue('persistent_note_missing', target, 'Parent persistent note target is not present in the replacement context.')
        return available, issue
    if scope == 'report_action':
        available = any(item['action_id'] == target.get('action_id') for item in context['actions'])
        issue = None if available else _review_issue('report_action_missing', target, 'Parent action target is not present in the replacement context.')
        return available, issue
    if scope == 'template_slot':
        available = target.get('slot_id') in _slot_ids(template_snapshot)
        issue = None if available else _review_issue('template_slot_removed', target, 'Parent slot is not present in the replacement template.')
        return available, issue
    return isinstance(edit, AuthoredEdit), None


def _historical_daily_note_already_in_context(edit, context):
    target = edit.target
    if not isinstance(target, Mapping) or target.get('scope') != 'daily_note':
        return False
    return any(note['note_id'] == target.get('note_id') for note in context['notes'])


def _review_issue(code, target, reason):
    return {'code': code, 'target': dict(target), 'reason': reason}


def _historical_reference_edit(edit, parent_draft, historical_resolver):
    records = tuple(_historical_reference_record(edit, record, parent_draft, historical_resolver) for record in tuple(edit.reference_observations or ()))
    return edit if not records else replace(edit, reference_observations=records)


def _historical_reference_record(edit, record, parent_draft, historical_resolver):
    if isinstance(record, Mapping) and record.get('schema_version') == 2:
        if historical_resolver is None or not historical_resolver(record):
            raise ReportError('REFERENCE_INVALID')
        record = _legacy_reference_record(record, edit)
    association = {
        'schema_version': 1,
        'kind': 'parent_draft_revision',
        'parent_draft_id': parent_draft.draft_id,
        'parent_draft_revision': parent_draft.revision,
        'parent_draft_revision_hash': parent_draft.revision_hash,
        'target_hash': canonical_hash(edit.target),
        'reference_id': record['reference_id'],
        'record_hash': _hash(record),
    }
    return {**record, 'schema_version': 2, 'historical_association': association}


def _publication_reference_edit(edit, publication):
    records = tuple(_publication_reference_record(edit, record, publication) for record in tuple(edit.reference_observations or ()))
    return edit if not records else replace(edit, reference_observations=records)


def _publication_reference_record(edit, record, publication):
    legacy = _legacy_reference_record(record, edit)
    association = {
        'schema_version': 1,
        'kind': 'source_publication',
        'publication_id': publication.manifest.publication_id,
        'manifest_hash': publication.manifest_sha256,
        'commit': publication.commit_id,
        'target_hash': canonical_hash(edit.target),
        'reference_id': legacy['reference_id'],
        'record_hash': _hash(legacy),
    }
    return {**legacy, 'schema_version': 2, 'historical_association': association}


def wrap_publication_reference_edits(publication, edits):
    return tuple(_publication_reference_edit(edit, publication) for edit in tuple(edits or ()))


def _legacy_reference_record(record, edit):
    if not isinstance(record, Mapping) or record.get('schema_version') != 2:
        return record
    expected = {
        'schema_version', 'reference_id', 'option_id', 'issued_fragment_hash',
        'content_basis', 'observation', 'historical_association',
    }
    if set(record) != expected:
        raise ReportError('REFERENCE_INVALID')
    legacy = {key: record[key] for key in (
        'reference_id', 'option_id', 'issued_fragment_hash', 'content_basis', 'observation',
    )}
    association = record['historical_association']
    if (not isinstance(association, Mapping)
            or association.get('kind') not in {'parent_draft_revision', 'source_publication'}
            or association.get('target_hash') != canonical_hash(edit.target)
            or association.get('reference_id') != legacy['reference_id']
            or association.get('record_hash') != _hash(legacy)):
        raise ReportError('REFERENCE_INVALID')
    return legacy


def _selected_publication_edits(edits):
    selected_revision = edits.get('selected_revision')
    if type(selected_revision) is not int or type(edits.get('revisions')) is not list:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    for item in edits['revisions']:
        if not isinstance(item, dict) or item.get('revision') != selected_revision:
            continue
        payload = item.get('payload')
        if not isinstance(payload, dict) or not isinstance(payload.get('edits'), list):
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        return tuple(authored_edit_from_mapping(edit) for edit in payload['edits'])
    raise ReportError('REPORT_HISTORY_UNAVAILABLE')


def _selected_publication_context(edits):
    selected_revision = edits.get('selected_revision')
    if type(selected_revision) is not int or type(edits.get('revisions')) is not list:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    for item in edits['revisions']:
        if not isinstance(item, dict) or item.get('revision') != selected_revision:
            continue
        payload = item.get('payload')
        if not isinstance(payload, dict) or payload.get('authoring_context') is None:
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        return validate_daily_authoring_context(payload['authoring_context'])
    raise ReportError('REPORT_HISTORY_UNAVAILABLE')


def _source_publication_edit_is_historical_only(edit, source_context, context):
    target = edit.target
    if not isinstance(target, Mapping):
        return False
    if target.get('scope') == 'daily_note':
        return _note_in_context(source_context, target.get('note_id')) and not _current_note_target(context, target.get('note_id'))
    if target.get('scope') == 'persistent_note':
        note = _persistent_note(source_context, target.get('note_id'))
        return (
            note is not None
            and note.get('carry_forward') is False
            and source_context['period'] != context['period']
        )
    return False


def _note_in_context(context, note_id):
    return any(note['note_id'] == note_id for note in context['notes'])


def _current_note_target(context, note_id):
    return any(observation['note_id'] == note_id for observation in context['current_observations'])


def _persistent_note(context, note_id):
    return next((note for note in context['persistent_notes'] if note['note_id'] == note_id), None)


def _slot_ids(template_snapshot):
    return {
        block['slot_id']
        for block in template_snapshot['resolved_document']['blocks']
        if block['kind'] == 'slot'
    }


def _human_note(note):
    return note['provenance'].get('origin') in {'human', 'ai_assisted'}


def _same_source_note(note, observation):
    return (
        note['source_status'].get('source_hash') == observation.get('source_hash')
        and note['provenance'].get('ai_result_ref') == observation.get('accepted_summary_ref')
    )


def _recompute_weekly_seed(context):
    weekly_seed = {
        **context['weekly_seed'],
        'unresolved_action_ids': tuple(
            action['action_id']
            for action in context['actions']
            if action.get('tracking_state') not in {'done', 'canceled'}
        ),
        'persistent_note_refs': tuple(note['note_id'] for note in context['persistent_notes']),
    }
    return {**context, 'weekly_seed': weekly_seed}


def _issue_key(issue_ref):
    return (issue_ref['provider_id'], issue_ref['endpoint_fingerprint'], issue_ref['stable_id'])


def _hash(value):
    try:
        return sha256_bytes(canonical_bytes(value))
    except ArchiveError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def _plain_json(value):
    try:
        return decode_json(canonical_bytes(value))
    except ArchiveError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
