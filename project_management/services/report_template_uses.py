from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import template_definition_from_mapping, validate_hash_text, validate_uuid_text
from project_management.app.domain.report_templates import PinnedTemplateUse
from project_management.models_report_templates import ReportTemplateCommand, ReportTemplateUse


def read_pinned_template_use(project, *, draft_id, template_use_hash):
    draft_id = validate_uuid_text(draft_id)
    template_use_hash = validate_hash_text(template_use_hash)
    matches = tuple(ReportTemplateUse.objects.filter(project=project, draft_id=draft_id, snapshot_hash=template_use_hash))
    if not matches:
        raise ReportError('REPORT_NOT_FOUND')
    if len(matches) != 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    use = matches[0]
    _verify_hash(use.snapshot_json, use.snapshot_hash)
    command = ReportTemplateCommand.objects.filter(project=project, command=use.command).first()
    if command is None:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    _verify_hash(command.payload_json, command.payload_hash)
    payload = command.payload_json.get('use_payload')
    if not _same_json(payload, use.snapshot_json):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if (command.kind != 'use' or command.request_hash != _command_hash(payload)
            or command.result_template_id != use.template_id or command.result_revision != use.revision
            or command.result_hash != use.revision_hash or command.payload_json.get('template_id') != str(use.template_id)
            or command.payload_json.get('revision_payload', {}).get('revision') != use.revision):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    expected = {'command_id', 'draft_id', 'request_hash', 'template_snapshot', 'template_definition'}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if payload['command_id'] != str(use.command) or payload['draft_id'] != str(use.draft_id):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return PinnedTemplateUse(
        payload['command_id'],
        payload['draft_id'],
        payload['request_hash'],
        payload['template_snapshot'],
        template_definition_from_mapping(payload['template_definition']),
    )


def _verify_hash(value, expected):
    try:
        if sha256_bytes(canonical_bytes(value)) != expected:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    except ArchiveError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def _command_hash(payload):
    selection = payload.get('template_snapshot', {}).get('selection')
    document = payload.get('template_snapshot', {}).get('resolved_document')
    use_mode = 'continuity_prepare' if isinstance(document, dict) and document.get('schema_version') == 2 else 'standalone'
    return sha256_bytes(canonical_bytes({
        'kind': 'use',
        'draft_id': payload.get('draft_id'),
        'request_hash': payload.get('request_hash'),
        'selection': selection,
        'use_mode': use_mode,
    }))


def _same_json(left, right):
    try:
        return canonical_bytes(left) == canonical_bytes(right)
    except ArchiveError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
