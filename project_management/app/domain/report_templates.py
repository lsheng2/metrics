from dataclasses import dataclass
from typing import Literal, Mapping
from uuid import UUID, uuid4
from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring_fragments import validate_rich_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_presentation import TemplateDefinition
from project_management.app.domain.report_template_presentation import (
    MANDATORY_DATA, RENDERER_VERSION, STANDUP_RENDERER_VERSION, is_pinned_renderer,
    template_renderer_version, template_readiness as _readiness,
)
MAX_DOCUMENT_POLICY_BYTES = 262_144
MAX_BLOCKS = 128
MAX_SLOTS = 64
MAX_INSTRUCTION_BYTES = 4096
MAX_INSTRUCTIONS_BYTES = 32768
@dataclass(frozen=True, slots=True)
class ReportTemplateLimits:
    max_templates: int = 100
    max_revisions: int = 100
    max_project_payload_bytes: int = 50 * 1024 * 1024
@dataclass(frozen=True, slots=True)
class TemplateSummary:
    template_id: str
    current_revision: int
    revision_hash: str
    name: str
    readiness: Literal['draft', 'ready']
    archived: bool
@dataclass(frozen=True, slots=True)
class TemplatePage:
    items: tuple[TemplateSummary, ...]
    next_offset: int | None
@dataclass(frozen=True, slots=True)
class ReportTemplateRevision:
    template_id: str | None
    revision: int | None
    revision_hash: str
    project_id: str | None
    name: str
    document: Mapping
    presentation_hash: str
    fill_policy: Mapping
    fill_policy_hash: str
    readiness: Literal['draft', 'ready']
    validation_codes: tuple[str, ...]
    created_by: str | None = None
    created_at: str | None = None
@dataclass(frozen=True, slots=True)
class UserTemplateSelection:
    template_id: str
    revision: int
    revision_hash: str
    origin: Literal['user'] = 'user'
@dataclass(frozen=True, slots=True)
class PinnedTemplateUse:
    command_id: str
    draft_id: str
    request_hash: str
    template_snapshot: Mapping
    template_definition: TemplateDefinition
def validate_report_template_revision(name, document, fill_policy) -> ReportTemplateRevision:
    name = _name(name)
    document = _document(document)
    fill_policy = _fill_policy(fill_policy, document)
    _size({'document': document, 'fill_policy': fill_policy}, MAX_DOCUMENT_POLICY_BYTES)
    readiness, codes = _readiness(document)
    return ReportTemplateRevision(
        None, None, _hash({'name': name, 'document': document, 'fill_policy': fill_policy}),
        None, name, document, template_document_presentation_hash(document),
        fill_policy, template_fill_policy_hash(fill_policy), readiness, codes,
    )
def template_document_presentation_hash(document) -> str:
    return _hash({'renderer_version': template_renderer_version(document), 'document': document})
def template_fill_policy_hash(fill_policy) -> str:
    return _hash(fill_policy)
def revision_from_payload(payload) -> ReportTemplateRevision:
    expected = {
        'template_id', 'revision', 'project_id', 'name', 'document', 'presentation_hash',
        'fill_policy', 'fill_policy_hash', 'readiness', 'validation_codes', 'created_by', 'created_at',
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    document = _document(payload['document'])
    fill_policy = _fill_policy(payload['fill_policy'], document)
    presentation_hash = _hash_text(payload['presentation_hash'])
    fill_policy_hash = _hash_text(payload['fill_policy_hash'])
    stored_readiness = _literal(payload['readiness'], {'draft', 'ready'})
    stored_codes = tuple(_str(item) for item in _list(payload['validation_codes']))
    readiness, validation_codes = _readiness(document)
    if (presentation_hash != template_document_presentation_hash(document)
            or fill_policy_hash != template_fill_policy_hash(fill_policy)
            or readiness != stored_readiness
            or validation_codes != stored_codes):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    revision_hash = _hash(payload)
    return ReportTemplateRevision(
        _uuid(payload['template_id']), _positive_int(payload['revision']),
        revision_hash, _uuid(payload['project_id']), _name(payload['name']),
        document, presentation_hash, fill_policy, fill_policy_hash,
        stored_readiness, stored_codes,
        _str(payload['created_by']), _str(payload['created_at']),
    )
def payload_for_revision(template_id, revision, project_id, actor_subject, created_at, validated):
    return {
        'template_id': _uuid(str(template_id)),
        'revision': _positive_int(revision),
        'project_id': _uuid(str(project_id)),
        'name': validated.name,
        'document': validated.document,
        'presentation_hash': validated.presentation_hash,
        'fill_policy': validated.fill_policy,
        'fill_policy_hash': validated.fill_policy_hash,
        'readiness': validated.readiness,
        'validation_codes': validated.validation_codes,
        'created_by': _str(actor_subject),
        'created_at': _str(created_at),
    }
def template_snapshot(selection: UserTemplateSelection, revision: ReportTemplateRevision):
    return {
        'selection': {
            'origin': 'user',
            'template_id': selection.template_id,
            'revision': selection.revision,
            'revision_hash': selection.revision_hash,
        },
        'resolved_document': revision.document,
        'presentation_hash': revision.presentation_hash,
        'fill_policy': revision.fill_policy,
        'fill_policy_hash': revision.fill_policy_hash,
        'renderer_version': template_renderer_version(revision.document),
    }
def validate_template_document_snapshot(value):
    expected = {'selection', 'resolved_document', 'presentation_hash', 'fill_policy', 'fill_policy_hash', 'renderer_version'}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if not is_pinned_renderer(value['renderer_version']):
        raise ReportError('REPORT_DOCUMENT_UNSUPPORTED')
    selection = _mapping(value['selection'])
    if set(selection) != {'origin', 'template_id', 'revision', 'revision_hash'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    selection = {
        'origin': _literal(selection['origin'], {'user'}),
        'template_id': _uuid(selection['template_id']),
        'revision': _positive_int(selection['revision']),
        'revision_hash': _hash_text(selection['revision_hash']),
    }
    document = _document(value['resolved_document'])
    if value['renderer_version'] != template_renderer_version(document):
        raise ReportError('REPORT_DOCUMENT_UNSUPPORTED')
    if document['schema_version'] not in {1, 2}:
        raise ReportError('REPORT_CONTEXT_REQUIRED')
    fill_policy = _fill_policy(value['fill_policy'], document)
    presentation_hash = _hash_text(value['presentation_hash'])
    fill_policy_hash = _hash_text(value['fill_policy_hash'])
    if (presentation_hash != template_document_presentation_hash(document)
            or fill_policy_hash != template_fill_policy_hash(fill_policy)):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {
        'selection': selection,
        'resolved_document': document,
        'presentation_hash': presentation_hash,
        'fill_policy': fill_policy,
        'fill_policy_hash': fill_policy_hash,
        'renderer_version': value['renderer_version'],
    }
def template_definition(revision: ReportTemplateRevision):
    return TemplateDefinition(
        revision.template_id, str(revision.revision), {}, revision.presentation_hash,
        template_renderer_version(revision.document),
    )
def copy_document_and_policy(document, fill_policy):
    slot_map = {}
    copied = []
    for block in document['blocks']:
        item = dict(block)
        item['block_id'] = str(uuid4())
        if item['kind'] == 'slot':
            old = item['slot_id']
            item['slot_id'] = str(uuid4())
            slot_map[old] = item['slot_id']
        if item['kind'] == 'data' and item['source'] == 'meeting_matrix':
            item['options'] = _copy_matrix_options(item['options'])
        copied.append(item)
    instructions = {slot_map[key]: value for key, value in fill_policy['instructions'].items() if key in slot_map}
    policy = {'schema_version': fill_policy['schema_version'], 'instructions': instructions}
    if fill_policy['schema_version'] == 2:
        policy['daily_note_instructions'] = fill_policy['daily_note_instructions']
    return {**document, 'blocks': copied}, policy
def _document(value):
    value = _mapping(value)
    expected = {'schema_version', 'report_kind', 'blocks'}
    if 'presentation_profile' in value:
        expected.add('presentation_profile')
    if set(value) != expected:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    version = _literal(value['schema_version'], {1, 2})
    report_kind = _literal(value['report_kind'], {'daily', 'weekly'})
    blocks = tuple(_block(block, version) for block in _list(value['blocks']))
    renderer = template_renderer_version(value)
    if renderer == STANDUP_RENDERER_VERSION and any(
            block['kind'] == 'data' and block['source'] != 'meeting_matrix' for block in blocks):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if len(blocks) > MAX_BLOCKS or sum(1 for block in blocks if block['kind'] == 'slot') > MAX_SLOTS:
        raise ReportError('REPORT_LIMIT')
    _unique(tuple(block['block_id'] for block in blocks))
    _unique(tuple(block['slot_id'] for block in blocks if block['kind'] == 'slot'))
    result = {'schema_version': version, 'report_kind': report_kind, 'blocks': blocks}
    if renderer == STANDUP_RENDERER_VERSION:
        result['presentation_profile'] = value['presentation_profile']
    return _plain_json(result)
def _block(value, version):
    value = _mapping(value)
    kind = _literal(value.get('kind'), {'content', 'slot', 'data'})
    if kind == 'content':
        if set(value) != {'kind', 'block_id', 'fragment'}:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        return {'kind': kind, 'block_id': _uuid(value['block_id']), 'fragment': _fragment(value['fragment'])}
    if kind == 'slot':
        if set(value) != {'kind', 'block_id', 'slot_id', 'label', 'required', 'initial', 'fill_mode'}:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        return {
            'kind': kind, 'block_id': _uuid(value['block_id']), 'slot_id': _uuid(value['slot_id']),
            'label': _bounded_text(value['label'], 160), 'required': _bool(value['required']),
            'initial': _fragment(value['initial']),
            'fill_mode': _literal(value['fill_mode'], {'manual', 'ai_optional'}),
        }
    if set(value) != {'kind', 'block_id', 'source', 'options'}:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    source = _literal(value['source'], set(MANDATORY_DATA + ('weekly_timeline',)) | ({'meeting_matrix'} if version == 2 else set()))
    options = _matrix_options(value['options']) if source == 'meeting_matrix' else _data_options(value['options'])
    return {'kind': kind, 'block_id': _uuid(value['block_id']), 'source': source, 'options': options}
def _data_options(value):
    value = _mapping(value)
    if set(value) != {'group_by', 'sort_by', 'optional_columns'}:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    columns = tuple(_literal(item, {'summary_time', 'source_hash'}) for item in _list(value['optional_columns']))
    _unique(columns)
    return {
        'group_by': _literal(value['group_by'], {'none', 'status', 'assignee'}),
        'sort_by': _literal(value['sort_by'], {'key'}),
        'optional_columns': columns,
    }
def _matrix_options(value):
    value = _mapping(value)
    expected = {
        'row_mode', 'order_mode', 'initial_sort', 'group_mode', 'groups', 'history_mode',
        'cross_week_carry', 'note_prefix', 'action_labels',
    }
    if set(value) != expected:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    groups = tuple(_matrix_group(group) for group in _list(value['groups']))
    if value['group_mode'] == 'none' and groups:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if value['group_mode'] == 'manual' and not groups:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    _unique(tuple(group['group_id'] for group in groups))
    _unique(tuple(group['rank'] for group in groups))
    labels = _mapping(value['action_labels'])
    if set(labels) != {'recorded', 'proposed'}:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return {
        'row_mode': _literal(value['row_mode'], {'one_ticket'}),
        'order_mode': _literal(value['order_mode'], {'stable_append'}),
        'initial_sort': _literal(value['initial_sort'], {'key_natural_asc'}),
        'group_mode': _literal(value['group_mode'], {'none', 'manual'}),
        'groups': groups,
        'history_mode': _literal(value['history_mode'], {'cumulative'}),
        'cross_week_carry': _literal(value['cross_week_carry'], {'last_confirmed_and_unresolved', 'full_history'}),
        'note_prefix': _literal(value['note_prefix'], {'workweek_day_source_status'}),
        'action_labels': {'recorded': _str(labels['recorded']), 'proposed': _str(labels['proposed'])},
    }
def _matrix_group(value):
    value = _mapping(value)
    if set(value) != {'group_id', 'label', 'rank'}:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return {'group_id': _uuid(value['group_id']), 'label': _bounded_text(value['label'], 160), 'rank': _nonnegative_int(value['rank'])}
def _fill_policy(value, document):
    value = _mapping(value)
    expected = {'schema_version', 'instructions'} if document['schema_version'] == 1 else {'schema_version', 'instructions', 'daily_note_instructions'}
    if set(value) != expected or value['schema_version'] != document['schema_version']:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    slots = {block['slot_id']: block for block in document['blocks'] if block['kind'] == 'slot'}
    instructions = {}
    total = 0
    for key, text in _mapping(value['instructions']).items():
        slot = slots.get(_uuid(key))
        if slot is None or slot['fill_mode'] != 'ai_optional':
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        text = _str(text)
        size = len(text.encode('utf-8'))
        if size > MAX_INSTRUCTION_BYTES:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        total += size
        instructions[key] = text
    if total > MAX_INSTRUCTIONS_BYTES:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    result = {'schema_version': document['schema_version'], 'instructions': instructions}
    if document['schema_version'] == 2:
        note = value['daily_note_instructions']
        if note is not None:
            note = _str(note)
            if len(note.encode('utf-8')) > MAX_INSTRUCTION_BYTES:
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        result['daily_note_instructions'] = note
    return _plain_json(result)
def _copy_matrix_options(options):
    copied = dict(options)
    copied['groups'] = [{**group, 'group_id': str(uuid4())} for group in options['groups']]
    return copied
def _fragment(value):
    try:
        return validate_rich_text_fragment(value)
    except ReportError:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED') from None
def _plain_json(value):
    try:
        return decode_json(canonical_bytes(_json(value)))
    except ArchiveError:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED') from None
def _json(value):
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
def _hash(value):
    try:
        return sha256_bytes(canonical_bytes(value))
    except ArchiveError:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED') from None
def _size(value, maximum):
    try:
        if len(canonical_bytes(value)) > maximum:
            raise ReportError('REPORT_LIMIT')
    except ArchiveError:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED') from None
def _mapping(value):
    if not isinstance(value, Mapping):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _list(value):
    if not isinstance(value, (list, tuple)):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _uuid(value):
    if type(value) is not str:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED') from None
    if str(parsed) != value.lower():
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _hash_text(value):
    if type(value) is not str or len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value
def _literal(value, allowed):
    if type(value) is not str and type(value) is not int:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if value not in allowed:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _str(value):
    if type(value) is not str:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _name(value):
    value = _bounded_text(value, 160)
    if not value:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _bounded_text(value, maximum):
    value = _str(value)
    if len(value) > maximum or any(ord(character) < 32 and character not in {'\n', '\r', '\t'} for character in value):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _bool(value):
    if type(value) is not bool:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _positive_int(value):
    if type(value) is not int or value < 1:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _nonnegative_int(value):
    if type(value) is not int or value < 0:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return value
def _unique(values):
    if len(values) != len(set(values)):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
