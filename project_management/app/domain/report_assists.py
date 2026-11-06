from dataclasses import asdict, dataclass
from typing import Mapping

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.report_authoring_fragments import (
    plain_text_fragment, rich_text_fragment_plain_text, validate_rich_text_fragment,
)
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_edits import source_key_hash, text_hash
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_validation import validate_generated_narrative


MAX_INPUT_BYTES = 131072
MAX_OUTPUT_BYTES = 65536
MAX_TARGETS = 8
MAX_OBSERVATIONS = 16
DEADLINE_SECONDS = 180


@dataclass(frozen=True, slots=True)
class AssistTarget:
    target_id: str
    target: Mapping
    kind: str
    fragment: Mapping
    fragment_hash: str
    expected_original_hash: str | None
    source_key: str | None


@dataclass(frozen=True, slots=True)
class AssistStatus:
    assist_id: str
    state: str
    candidate: Mapping | None = None
    error_code: str | None = None


def available_targets(draft):
    context = draft.authoring_context
    if (draft.state != 'draft' or draft.authoring_schema != 'report-authoring/2'
            or context is not None and context.get('report_role') != 'daily'):
        return ()
    active = {}
    for edit in draft.authored_edits:
        active.setdefault(content_hash(edit.target), []).append(edit)
    targets = []

    def add(target, kind, fragment, expected=None, key=None):
        target_id = content_hash(target)
        old = active.get(target_id, ())
        if len(old) > 1:
            return
        if old:
            fragment = old[0].fragment
        fragment = validate_rich_text_fragment(fragment)
        targets.append(AssistTarget(target_id, target, kind, fragment, content_hash(fragment), expected, key))

    add({'scope': 'report'}, 'note', plain_text_fragment(''))
    for row in draft.snapshot.rows:
        key = source_key_hash(row.source_key)
        add({'scope': 'issue', 'source_key_hash': key}, 'note', plain_text_fragment(''), key=key)
        for field in ('what', 'current_position', 'verification'):
            text = getattr(row, field) or ''
            add({'scope': 'issue', 'source_key_hash': key, 'field': field}, 'narrative_override',
                plain_text_fragment(text), text_hash(text), key)
        if row.summary_ref is not None:
            for index, action in enumerate(row.next_actions):
                text = action.get('action') or ''
                add({'scope': 'action', 'source_key_hash': key, 'summary_id': row.summary_ref.summary_id,
                     'action_index': index, 'field': 'action'}, 'narrative_override',
                    plain_text_fragment(text), text_hash(text), key)
    if context is not None:
        notes = {note['note_id']: note for note in context['notes']}
        for item in context['current_observations']:
            note = notes.get(item['note_id'])
            add({'scope': 'daily_note', 'note_id': item['note_id']}, 'note',
                plain_text_fragment('') if note is None else note['body_fragment'],
                None if note is None else note['body_hash'], _issue_key(draft, item['issue_ref']))
        for item in context['persistent_notes']:
            add({'scope': 'persistent_note', 'note_id': item['note_id']}, 'note', item['fragment'],
                key=None if item['issue_ref'] is None else _issue_key(draft, item['issue_ref']))
        for item in context['actions']:
            add({'scope': 'report_action', 'action_id': item['action_id']}, 'note', item['body_fragment'],
                key=_issue_key(draft, item['issue_ref']))
    for block in draft.template_snapshot['resolved_document']['blocks']:
        if block['kind'] == 'slot' and block['fill_mode'] == 'ai_optional':
            add({'scope': 'template_slot', 'slot_id': block['slot_id']}, 'slot_fill', block['initial'])
    return tuple(targets)


def build_assist_input(draft, target_ids, instruction):
    if type(instruction) is not str or not instruction.strip() or len(instruction.encode('utf-8')) > 4000:
        raise ReportError('REPORT_INVALID')
    ids = tuple(target_ids)
    if not 1 <= len(ids) <= MAX_TARGETS or any(type(value) is not str for value in ids) or len(ids) != len(set(ids)):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    available = {item.target_id: item for item in available_targets(draft)}
    if any(value not in available for value in ids):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    targets = [available[value] for value in sorted(ids)]
    selected_keys = {item.source_key for item in targets}
    evidence = []
    urls = set()
    for row in draft.snapshot.rows:
        key = source_key_hash(row.source_key)
        if None not in selected_keys and key not in selected_keys:
            continue
        evidence.append({
            'ref_id': f'record:{key}', 'source_key': key, 'source_hash': row.source_hash,
            'capture_id': draft.snapshot.capture_id, 'kind': 'source_snapshot',
            'value': {'title': row.title, 'status': row.status, 'assignee': row.assignee},
        })
        if row.source_url:
            urls.add(row.source_url)
        for record in row.evidence:
            evidence.append({**record, 'ref_id': f"{key}:{record['ref_id']}", 'source_key': key})
    for item in targets:
        urls.update(node['href'] for node in _nodes(item.fragment) if node.get('type') == 'link')
    value = {
        'schema_version': 1,
        'draft': {
            'draft_id': draft.draft_id, 'revision': draft.revision, 'revision_hash': draft.revision_hash,
            'project_id': draft.snapshot.project_id, 'stage_id': draft.snapshot.stage_id,
            'actor': draft.snapshot.owner_subject, 'snapshot_hash': draft.snapshot_hash,
            'template_hash': content_hash(draft.template_snapshot),
            'fill_policy_hash': draft.template_snapshot['fill_policy_hash'],
        },
        'targets': [asdict(item) for item in targets],
        'evidence': evidence,
        'allowed_urls': sorted(urls),
        'fill_policy': draft.template_snapshot['fill_policy'],
        'instruction': instruction,
    }
    payload = canonical_bytes(value)
    if len(payload) > MAX_INPUT_BYTES or len(evidence) > 256:
        raise ReportError('REPORT_LIMIT')
    return decode_json(payload)


def validate_assist_output(source, candidate):
    if (not isinstance(candidate, Mapping) or set(candidate) != {'schema_version', 'targets'}
            or type(candidate['schema_version']) is not int or candidate['schema_version'] != 1
            or type(candidate['targets']) is not list or len(canonical_bytes(candidate)) > MAX_OUTPUT_BYTES):
        raise ReportError('REPORT_AI_RESULT_INVALID')
    expected = {row['target_id']: row for row in source['targets']}
    evidence = {row['ref_id']: row for row in source['evidence']}
    seen = set()
    output = []
    for item in candidate['targets']:
        if (not isinstance(item, dict) or set(item) != {'target_id', 'status', 'fragment', 'evidence_refs', 'reason_code'}
                or type(item['target_id']) is not str or item['target_id'] not in expected
                or item['target_id'] in seen or type(item['evidence_refs']) is not list
                or any(type(ref) is not str or ref not in evidence for ref in item['evidence_refs'])
                or len(item['evidence_refs']) != len(set(item['evidence_refs']))):
            raise ReportError('REPORT_AI_RESULT_INVALID')
        seen.add(item['target_id'])
        allowed_key = expected[item['target_id']]['source_key']
        if allowed_key is not None and any(evidence[ref]['source_key'] != allowed_key for ref in item['evidence_refs']):
            raise ReportError('REPORT_AI_RESULT_INVALID')
        if item['status'] == 'insufficient_evidence':
            if (item['fragment'] is not None or item['evidence_refs'] or type(item['reason_code']) is not str
                    or item['reason_code'] not in {'source_missing', 'source_incomplete', 'no_supported_conclusion'}):
                raise ReportError('REPORT_AI_RESULT_INVALID')
            output.append(item)
            continue
        if item['status'] != 'filled' or item['reason_code'] is not None or not item['evidence_refs']:
            raise ReportError('REPORT_AI_RESULT_INVALID')
        fragment = validate_rich_text_fragment(item['fragment'])
        for node in _nodes(fragment):
            if 'reference_id' in node or node.get('type') == 'link' and node['href'] not in source['allowed_urls']:
                raise ReportError('REPORT_AI_RESULT_INVALID')
        try:
            validate_generated_narrative(rich_text_fragment_plain_text(fragment),
                                         tuple(evidence[ref]['value'] for ref in item['evidence_refs']))
        except AnalysisError:
            raise ReportError('REPORT_AI_RESULT_INVALID') from None
        output.append({**item, 'fragment': fragment})
    if seen != set(expected):
        raise ReportError('REPORT_AI_RESULT_INVALID')
    return decode_json(canonical_bytes({'schema_version': 1, 'targets': output}))


def _issue_key(draft, issue_ref):
    rows = [row for row in draft.snapshot.rows if row.identity.provider_id == issue_ref['provider_id']
            and row.identity.stable_id == issue_ref['stable_id']]
    if len(rows) != 1:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return source_key_hash(rows[0].source_key)


def _nodes(value):
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _nodes(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _nodes(item)
