from dataclasses import fields
from datetime import UTC, datetime, timedelta
import re
import uuid
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.report_presentation import TemplateSelection
from project_management.app.domain.run_contracts import (
    ItemRunResult,
    RunError,
    RunOperation,
    RunPolicy,
    RunRequest,
)
from project_management.app.domain.run_item_values import validate_item_progress
from project_management.app.domain.summary_contracts import AiBackendTarget


RUN_STATES = {
    'queued',
    'capturing',
    'analyzing',
    'draft_ready',
    'partial',
    'cancel_requested',
    'canceled',
    'failed',
    'interrupted',
}
TERMINAL_STATES = {'draft_ready', 'partial', 'canceled', 'failed'}
NONTERMINAL_STATES = RUN_STATES - TERMINAL_STATES
ALLOWED_TRANSITIONS = {
    'queued': {'capturing', 'canceled', 'interrupted', 'failed', 'queued'},
    'capturing': {'analyzing', 'partial', 'cancel_requested', 'interrupted', 'failed', 'capturing'},
    'analyzing': {'analyzing', 'draft_ready', 'partial', 'cancel_requested', 'interrupted', 'failed'},
    'cancel_requested': {'canceled', 'interrupted', 'partial', 'cancel_requested'},
    'interrupted': {'queued', 'cancel_requested', 'canceled', 'partial', 'failed', 'interrupted'},
    'draft_ready': {'draft_ready'},
    'partial': {'partial'},
    'canceled': {'canceled'},
    'failed': {'failed'},
}
ITEM_STATES = {'pending', 'running', 'accepted', 'no_work', 'rejected', 'unknown', 'canceled'}


def validate_policy(policy: RunPolicy | None) -> RunPolicy:
    policy = policy or RunPolicy()
    if not isinstance(policy, RunPolicy):
        raise RunError('RUN_INVALID')
    values = {
        'timeout_seconds': (policy.timeout_seconds, 1, 600),
        'max_analysis_items': (policy.max_analysis_items, 1, 100),
        'max_observations_per_attempt': (policy.max_observations_per_attempt, 1, 16),
        'max_queued_operations': (policy.max_queued_operations, 1, 128),
    }
    for value, minimum, maximum in values.values():
        if type(value) is not int or not minimum <= value <= maximum:
            raise RunError('RUN_INVALID')
    return policy


def validate_request(request: RunRequest) -> RunRequest:
    if not isinstance(request, RunRequest):
        raise RunError('RUN_INVALID')
    validate_uuid_text(request.command_id)
    validate_hash_text(request.expected_stage_hash)
    validate_template(request.template)
    validate_timezone(request.timezone)
    return request


def normalize_template(renderer, template: TemplateSelection) -> TemplateSelection:
    validate_template(template)
    try:
        definition = renderer.template_definition(template)
    except Exception:
        raise RunError('RUN_INVALID') from None
    return TemplateSelection(template.template_id, template.version, definition.options)


def normalized_request(request: RunRequest, template: TemplateSelection) -> RunRequest:
    return RunRequest(request.command_id, request.expected_stage_hash, template, request.timezone)


def request_hash(request: RunRequest) -> str:
    return content_hash(request_payload(request))


def policy_hash(policy: RunPolicy) -> str:
    return content_hash(policy_payload(policy))


def operation_id(stage_id: str, command_id: str) -> str:
    return str(uuid.uuid5(uuid.UUID(validate_uuid_text(stage_id)), f'run:{validate_uuid_text(command_id)}'))


def capture_id(operation_id_value: str) -> str:
    return str(uuid.uuid5(uuid.UUID(validate_uuid_text(operation_id_value)), 'capture'))


def draft_command_id(operation_id_value: str) -> str:
    return str(uuid.uuid5(uuid.UUID(validate_uuid_text(operation_id_value)), 'draft'))


def utc_instant_millis(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RunError('RUN_INVALID')
    return value.astimezone(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def deadline_from(created_at: str, policy: RunPolicy) -> str:
    return utc_instant_millis(parse_instant(created_at) + timedelta(seconds=policy.timeout_seconds))


def parse_instant(value: str) -> datetime:
    if type(value) is not str:
        raise RunError('RUN_INVALID')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise RunError('RUN_INVALID') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RunError('RUN_INVALID')
    return parsed.astimezone(UTC)


def operation_from_mapping(value: Mapping) -> RunOperation:
    required = {field.name for field in fields(RunOperation)}
    if set(value) != required:
        raise RunError('RUN_STORAGE_INVALID')
    operation = RunOperation(
        operation_id=validate_uuid_text(value['operation_id']),
        command_id=validate_uuid_text(value['command_id']),
        project_id=validate_uuid_text(value['project_id']),
        stage_id=validate_uuid_text(value['stage_id']),
        actor_subject=text(value['actor_subject'], 160),
        stage_hash=validate_hash_text(value['stage_hash']),
        policy_hash=validate_hash_text(value['policy_hash']),
        created_at=utc_instant_millis(parse_instant(value['created_at'])),
        deadline_at=utc_instant_millis(parse_instant(value['deadline_at'])),
        capture_id=validate_uuid_text(value['capture_id']),
        state=state_text(value['state']),
        revision=positive_revision(value['revision']),
        cancel_requested=bool_value(value['cancel_requested']),
        item_results=tuple(item_result_from_mapping(row) for row in list_value(value['item_results'])),
        draft_id=optional_uuid(value['draft_id']),
        draft_revision=optional_positive_int(value['draft_revision']),
        draft_revision_hash=optional_hash(value['draft_revision_hash']),
        snapshot_hash=optional_hash(value['snapshot_hash']),
        template_hash=optional_hash(value['template_hash']),
        error_code=optional_error(value['error_code']),
        execution_mode=literal(value['execution_mode'], 'synthetic'),
    )
    if operation.capture_id != capture_id(operation.operation_id):
        raise RunError('RUN_STORAGE_INVALID')
    return operation


def item_result_from_mapping(value: Mapping) -> ItemRunResult:
    if set(value) != {'source_key_hash', 'state', 'attempt_id', 'accepted_summary_id', 'error_code'}:
        raise RunError('RUN_STORAGE_INVALID')
    state = text(value['state'], 80)
    if state not in ITEM_STATES:
        raise RunError('RUN_STORAGE_INVALID')
    return ItemRunResult(
        validate_hash_text(value['source_key_hash']),
        state,
        optional_uuid(value['attempt_id']),
        optional_uuid(value['accepted_summary_id']),
        optional_error(value['error_code']),
    )


def request_from_mapping(value: Mapping) -> RunRequest:
    if set(value) != {'command_id', 'expected_stage_hash', 'template', 'timezone'}:
        raise RunError('RUN_STORAGE_INVALID')
    template = value['template']
    if not isinstance(template, Mapping) or set(template) != {'template_id', 'version', 'options'}:
        raise RunError('RUN_STORAGE_INVALID')
    request = RunRequest(
        validate_uuid_text(value['command_id']),
        validate_hash_text(value['expected_stage_hash']),
        TemplateSelection(text(template['template_id']), text(template['version']), mapping_value(template['options'])),
        text(value['timezone'], 128),
    )
    return validate_request(request)


def policy_from_mapping(value: Mapping) -> RunPolicy:
    if set(value) != {'timeout_seconds', 'max_analysis_items', 'max_observations_per_attempt', 'max_queued_operations'}:
        raise RunError('RUN_STORAGE_INVALID')
    try:
        return validate_policy(RunPolicy(
            int_value(value['timeout_seconds']),
            int_value(value['max_analysis_items']),
            int_value(value['max_observations_per_attempt']),
            int_value(value['max_queued_operations']),
        ))
    except RunError:
        raise


def backend_from_mapping(value: Mapping) -> AiBackendTarget:
    if set(value) != {'base_url', 'source_app_id', 'run_store_id', 'scope_key', 'grant_revision', 'limit_policy_revision'}:
        raise RunError('RUN_STORAGE_INVALID')
    return AiBackendTarget(
        text(value['base_url'], 2048),
        text(value['source_app_id'], 256),
        text(value['run_store_id'], 256),
        text(value['scope_key'], 2048),
        text(value['grant_revision'], 256),
        text(value['limit_policy_revision'], 256),
    )


def request_payload(request: RunRequest):
    return {
        'command_id': request.command_id,
        'expected_stage_hash': request.expected_stage_hash,
        'template': template_payload(request.template),
        'timezone': request.timezone,
    }


def template_payload(template: TemplateSelection):
    return {
        'template_id': template.template_id,
        'version': template.version,
        'options': template.options,
    }


def policy_payload(policy: RunPolicy):
    return {
        'timeout_seconds': policy.timeout_seconds,
        'max_analysis_items': policy.max_analysis_items,
        'max_observations_per_attempt': policy.max_observations_per_attempt,
        'max_queued_operations': policy.max_queued_operations,
    }


def decode_mapping(data: bytes) -> Mapping:
    value = decode_json(data)
    if not isinstance(value, Mapping):
        raise RunError('RUN_STORAGE_INVALID')
    return value


def validate_transition(current: RunOperation, candidate: RunOperation) -> None:
    if current.operation_id != candidate.operation_id:
        raise RunError('RUN_REVISION_CONFLICT')
    immutable = (
        'operation_id',
        'command_id',
        'project_id',
        'stage_id',
        'actor_subject',
        'stage_hash',
        'policy_hash',
        'created_at',
        'deadline_at',
        'capture_id',
        'execution_mode',
    )
    if any(getattr(current, name) != getattr(candidate, name) for name in immutable):
        raise RunError('RUN_REVISION_CONFLICT')
    if current.state in TERMINAL_STATES:
        raise RunError('RUN_REVISION_CONFLICT')
    if candidate.revision != current.revision + 1:
        raise RunError('RUN_REVISION_CONFLICT')
    if candidate.state not in ALLOWED_TRANSITIONS[current.state]:
        raise RunError('RUN_REVISION_CONFLICT')
    if current.cancel_requested and not candidate.cancel_requested:
        raise RunError('RUN_REVISION_CONFLICT')
    if current.draft_id is not None and candidate.draft_id != current.draft_id:
        raise RunError('RUN_REVISION_CONFLICT')
    if current.draft_revision is not None and candidate.draft_revision != current.draft_revision:
        raise RunError('RUN_REVISION_CONFLICT')
    validate_item_progress(current.item_results, candidate.item_results)


def validate_uuid_text(value) -> str:
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value) is None:
        raise RunError('RUN_INVALID')
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise RunError('RUN_INVALID') from None


def validate_hash_text(value) -> str:
    if type(value) is not str or re.fullmatch(r'[a-f0-9]{64}', value) is None:
        raise RunError('RUN_INVALID')
    return value


def validate_template(template):
    if not isinstance(template, TemplateSelection):
        raise RunError('RUN_INVALID')
    text(template.template_id, 160)
    text(template.version, 80)
    mapping_value(template.options)
    canonical_bytes(template.options)


def validate_timezone(value):
    text(value, 128)
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise RunError('RUN_INVALID') from None


def text(value, limit=2048):
    if type(value) is not str or not value or len(value) > limit or value != value.strip() or any(ord(char) < 32 for char in value):
        raise RunError('RUN_INVALID')
    return value


def mapping_value(value):
    if not isinstance(value, Mapping):
        raise RunError('RUN_STORAGE_INVALID')
    return value


def list_value(value):
    if not isinstance(value, list):
        raise RunError('RUN_STORAGE_INVALID')
    return value


def int_value(value):
    if type(value) is not int:
        raise RunError('RUN_INVALID')
    return value


def positive_revision(value):
    if type(value) is not int or value < 1:
        raise RunError('RUN_STORAGE_INVALID')
    return value


def optional_positive_int(value):
    if value is None:
        return None
    if type(value) is not int or value < 1:
        raise RunError('RUN_STORAGE_INVALID')
    return value


def bool_value(value):
    if type(value) is not bool:
        raise RunError('RUN_STORAGE_INVALID')
    return value


def optional_uuid(value):
    if value is None:
        return None
    try:
        return validate_uuid_text(value)
    except RunError:
        raise RunError('RUN_STORAGE_INVALID') from None


def optional_hash(value):
    if value is None:
        return None
    try:
        return validate_hash_text(value)
    except RunError:
        raise RunError('RUN_STORAGE_INVALID') from None


def optional_error(value):
    if value is None:
        return None
    if type(value) is not str or not value or len(value) > 80 or re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}|[a-z][a-z0-9_]{0,79}', value) is None:
        raise RunError('RUN_STORAGE_INVALID')
    return value


def state_text(value):
    value = text(value, 80)
    if value not in RUN_STATES:
        raise RunError('RUN_STORAGE_INVALID')
    return value


def literal(value, expected):
    if value != expected:
        raise RunError('RUN_STORAGE_INVALID')
    return expected
