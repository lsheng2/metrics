from uuid import UUID, uuid5

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_preparation_validation import (
    request_payload_from_intent,
    validate_intent_nested_payload,
)
from project_management.app.domain.run_values import (
    capture_id as run_capture_id,
    draft_command_id as run_draft_command_id,
    operation_id as run_operation_id,
)


def validate_reprepare_intent(value, repository, hash_value):
    expected = {
        'schema_version', 'kind', 'preparation_id', 'slot_id', 'slot_key', 'project_id',
        'stage_id', 'owner_subject', 'command_id', 'request_hash', 'series_id',
        'series_policy_hash', 'meeting_date', 'meeting_key', 'period_key',
        'expected_baseline_ref', 'timezone', 'template_selection', 'source_mode',
        'capture_id', 'analysis_mode', 'acknowledge_gap_draft_ids',
        'effective_selection', 'effective_selection_hash', 'operation_command_id',
        'derived_operation_id', 'operation_id', 'draft_command_id', 'draft_id',
        'template_use_command_id', 'created_at', 'parent_preparation_id',
        'parent_intent_hash', 'parent_operation_id', 'expected_parent_operation_revision',
        'expected_parent_operation_state', 'parent_draft_id',
        'expected_parent_draft_revision', 'expected_parent_draft_revision_hash',
        'stage_hash', 'preparation_intent_hash', 'run_request_hash',
        'reprepare_intent_hash',
    }
    if not isinstance(value, dict) or set(value.keys()) != expected or value['kind'] != 'daily_reprepare':
        raise ReportError('REPORT_ARTIFACT_INVALID')
    _ids(value)
    _hashes(value)
    _modes(value)
    _parent(value)
    validate_intent_nested_payload(value)
    _binding(value, repository, hash_value)
    _hash_binding(value, hash_value)
    return value


def _ids(value):
    for key in (
        'preparation_id', 'slot_id', 'project_id', 'stage_id', 'command_id',
        'series_id', 'operation_command_id', 'derived_operation_id',
        'draft_command_id', 'draft_id', 'template_use_command_id',
        'capture_id', 'parent_preparation_id',
    ):
        validate_uuid_text(value[key])
    if value['parent_operation_id'] is not None:
        validate_uuid_text(value['parent_operation_id'])
    if value['operation_id'] is not None:
        validate_uuid_text(value['operation_id'])
    if value['parent_draft_id'] is not None:
        validate_uuid_text(value['parent_draft_id'])


def _hashes(value):
    for key in ('request_hash', 'series_policy_hash', 'effective_selection_hash', 'parent_intent_hash',
                'stage_hash', 'reprepare_intent_hash'):
        validate_hash_text(value[key])
    if value['preparation_intent_hash'] is not None:
        validate_hash_text(value['preparation_intent_hash'])
    if value['run_request_hash'] is not None:
        validate_hash_text(value['run_request_hash'])


def _modes(value):
    if value['source_mode'] not in {'saved_capture', 'refresh'} or value['analysis_mode'] not in {'manual_only', 'changed_items'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_mode'] == 'saved_capture' and value['analysis_mode'] != 'manual_only':
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_mode'] == 'refresh':
        if value['operation_id'] is None or value['preparation_intent_hash'] is None or value['run_request_hash'] is None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    elif value['operation_id'] is not None or value['preparation_intent_hash'] is not None or value['run_request_hash'] is not None:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _parent(value):
    if value['parent_operation_id'] is None:
        if value['expected_parent_operation_revision'] is not None or value['expected_parent_operation_state'] is not None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    else:
        if type(value['expected_parent_operation_revision']) is not int or value['expected_parent_operation_revision'] < 1:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['expected_parent_operation_state'] not in {'draft_ready', 'partial', 'canceled', 'failed'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['parent_draft_id'] is None:
        if value['expected_parent_draft_revision'] is not None or value['expected_parent_draft_revision_hash'] is not None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return
    if type(value['expected_parent_draft_revision']) is not int or value['expected_parent_draft_revision'] < 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    validate_hash_text(value['expected_parent_draft_revision_hash'])


def _binding(value, repository, hash_value):
    operation_id = run_operation_id(value['stage_id'], value['operation_command_id'])
    draft_command_id = run_draft_command_id(operation_id)
    effective_capture_id = run_capture_id(operation_id)
    if (
            value['slot_id'] != str(uuid5(UUID(value['series_id']), f"daily:{value['meeting_date']}"))
            or value['preparation_id'] != str(uuid5(UUID(value['parent_preparation_id']), f"reprepare:{value['command_id']}"))
            or value['derived_operation_id'] != operation_id
            or value['draft_command_id'] != draft_command_id
            or value['draft_id'] != str(uuid5(UUID(value['stage_id']), f'draft:{draft_command_id}'))
            or value['template_use_command_id'] != str(uuid5(UUID(value['preparation_id']), 'template-use'))):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_mode'] == 'refresh' and (
            value['operation_id'] != operation_id
            or value['capture_id'] != effective_capture_id
            or value['effective_selection']['capture_id'] != effective_capture_id):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_mode'] == 'saved_capture' and (
            value['operation_id'] is not None
            or value['effective_selection']['capture_id'] != value['capture_id']):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['slot_key'] != {'series_id': value['series_id'], 'local_date': value['meeting_date']}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['project_id'] != repository.project.id or value['stage_id'] != repository.stage.id:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['owner_subject'] != repository.owner_subject:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['request_hash'] != hash_value(request_payload_from_intent(value)):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['effective_selection_hash'] != hash_value(value['effective_selection']):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _hash_binding(value, hash_value):
    intent_hash_payload = {key: item for key, item in value.items() if key not in {'preparation_intent_hash', 'run_request_hash', 'reprepare_intent_hash'}}
    if value['preparation_intent_hash'] is not None and value['preparation_intent_hash'] != hash_value(intent_hash_payload):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['reprepare_intent_hash'] != hash_value(intent_hash_payload):
        raise ReportError('REPORT_ARTIFACT_INVALID')
