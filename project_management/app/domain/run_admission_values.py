from typing import Mapping

from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.run_contracts import RunError, RunOperation
from project_management.app.domain.run_values import (
    backend_from_mapping,
    bool_value,
    capture_id,
    int_value,
    literal,
    mapping_value,
    operation_id,
    parse_instant,
    policy_from_mapping,
    policy_hash,
    policy_payload,
    request_from_mapping,
    request_hash,
    request_payload,
    text,
    utc_instant_millis,
    validate_hash_text,
    validate_uuid_text,
)
from project_management.app.domain.summary_contracts import AiBackendTarget


def backend_payload(backend: AiBackendTarget):
    return {
        'base_url': backend.base_url,
        'source_app_id': backend.source_app_id,
        'run_store_id': backend.run_store_id,
        'scope_key': backend.scope_key,
        'grant_revision': backend.grant_revision,
        'limit_policy_revision': backend.limit_policy_revision,
    }


def capture_limits_payload(limits):
    if isinstance(limits, Mapping):
        return capture_limits_from_mapping(limits)
    return {
        'max_requests': int_value(limits.max_requests),
        'max_download_bytes': int_value(limits.max_download_bytes),
        'max_response_bytes': int_value(limits.max_response_bytes),
        'max_members': int_value(limits.max_members),
        'max_details': int_value(limits.max_details),
        'max_comments_per_item': int_value(limits.max_comments_per_item),
        'max_history_per_item': int_value(limits.max_history_per_item),
        'page_size': int_value(limits.page_size),
    }


def capture_limits_from_mapping(value: Mapping):
    expected = {
        'max_requests',
        'max_download_bytes',
        'max_response_bytes',
        'max_members',
        'max_details',
        'max_comments_per_item',
        'max_history_per_item',
        'page_size',
    }
    if set(value) != expected:
        raise RunError('RUN_STORAGE_INVALID')
    return {key: int_value(value[key]) for key in expected}


def stored_request_payload(operation: RunOperation, request, policy, backend: AiBackendTarget,
                           request_hash_value: str, capture_limits=None):
    payload = {
        'schema_version': 1,
        'operation_id': operation.operation_id,
        'project_id': operation.project_id,
        'stage_id': operation.stage_id,
        'actor_subject': operation.actor_subject,
        'command_id': operation.command_id,
        'request_hash': request_hash_value,
        'request': request_payload(request),
        'policy': policy_payload(policy),
        'policy_hash': operation.policy_hash,
        'created_at': operation.created_at,
        'deadline_at': operation.deadline_at,
        'capture_id': operation.capture_id,
        'backend': backend_payload(backend),
        'capture_limits': capture_limits_payload(capture_limits) if capture_limits is not None else None,
        'execution_mode': operation.execution_mode,
        'stage_hash': operation.stage_hash,
    }
    payload['admission_hash'] = admission_hash(payload)
    return payload


def validate_stored_request(value: Mapping):
    expected = {
        'schema_version',
        'operation_id',
        'project_id',
        'stage_id',
        'actor_subject',
        'command_id',
        'request_hash',
        'request',
        'policy',
        'policy_hash',
        'created_at',
        'deadline_at',
        'capture_id',
        'backend',
        'capture_limits',
        'execution_mode',
        'stage_hash',
        'admission_hash',
    }
    if set(value) != expected or value['schema_version'] != 1:
        raise RunError('RUN_STORAGE_INVALID')
    request = request_from_mapping(mapping_value(value['request']))
    policy = policy_from_mapping(mapping_value(value['policy']))
    backend = backend_from_mapping(mapping_value(value['backend']))
    capture_limits = capture_limits_from_mapping(mapping_value(value['capture_limits']))
    request_hash_value = validate_hash_text(value['request_hash'])
    admission_hash_value = validate_hash_text(value['admission_hash'])
    if request_hash(request) != request_hash_value:
        raise RunError('RUN_STORAGE_INVALID')
    if admission_hash(value) != admission_hash_value:
        raise RunError('RUN_STORAGE_INVALID')
    op_id = validate_uuid_text(value['operation_id'])
    cap_id = validate_uuid_text(value['capture_id'])
    if cap_id != capture_id(op_id):
        raise RunError('RUN_STORAGE_INVALID')
    if operation_id(validate_uuid_text(value['stage_id']), request.command_id) != op_id:
        raise RunError('RUN_STORAGE_INVALID')
    if value['command_id'] != request.command_id:
        raise RunError('RUN_STORAGE_INVALID')
    if validate_hash_text(value['policy_hash']) != policy_hash(policy):
        raise RunError('RUN_STORAGE_INVALID')
    if backend.scope_key != f"projects.{value['project_id']}.stages.{value['stage_id']}":
        raise RunError('RUN_STORAGE_INVALID')
    if parse_instant(value['deadline_at']) <= parse_instant(value['created_at']):
        raise RunError('RUN_STORAGE_INVALID')
    return request, policy, backend, request_hash_value, capture_limits


def admission_hash(value: Mapping):
    return content_hash({
        key: item for key, item in value.items()
        if key not in {'request_hash', 'admission_hash'}
    })


def original_operation_from_record(value: Mapping) -> RunOperation:
    request, _, _, _, _ = validate_stored_request(value)
    return RunOperation(
        operation_id=value['operation_id'],
        command_id=request.command_id,
        project_id=validate_uuid_text(value['project_id']),
        stage_id=validate_uuid_text(value['stage_id']),
        actor_subject=text(value['actor_subject'], 160),
        stage_hash=validate_hash_text(value['stage_hash']),
        policy_hash=validate_hash_text(value['policy_hash']),
        created_at=utc_instant_millis(parse_instant(value['created_at'])),
        deadline_at=utc_instant_millis(parse_instant(value['deadline_at'])),
        capture_id=validate_uuid_text(value['capture_id']),
        state='queued',
        revision=1,
        cancel_requested=False,
        item_results=(),
        draft_id=None,
        draft_revision=None,
        draft_revision_hash=None,
        snapshot_hash=None,
        template_hash=None,
        error_code=None,
        execution_mode=literal(value['execution_mode'], 'synthetic'),
    )
