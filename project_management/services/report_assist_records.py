from datetime import UTC, timedelta
from uuid import UUID, uuid5

from project_management.app.domain.capture_values import canonical_bytes, json_value, sha256_bytes
from project_management.app.domain.captures import ArchiveError, SourceChainKey
from project_management.app.domain.report_assists import DEADLINE_SECONDS
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AnalysisAttempt, AnalysisError, PreparedAnalysis
from project_management.app.domain.task_run_codec import (
    cancellation_from_record, principal_from_record, request_from_record, result_from_record, snapshot_from_record,
)
from project_management.app.domain.task_runs import TaskPrincipal


def assist_id_for(draft_id, command_id):
    return str(uuid5(UUID(draft_id), 'assist:' + str(UUID(command_id))))


def _prepared(value, digest):
    draft = value['draft']
    key = SourceChainKey('report', 'report', draft['draft_id'], draft['actor'], draft['snapshot_hash'])
    return PreparedAnalysis(
        key, draft['draft_id'], draft['snapshot_hash'], draft['revision'], None,
        canonical_bytes(value).decode('utf-8'), digest,
    )


def make_intent(draft, command_id, input_value, contract, principal, now):
    if (not isinstance(principal, TaskPrincipal)
            or principal.subject != input_value['draft']['actor']
            or input_value['draft']['draft_id'] != draft.draft_id):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    assist_id = assist_id_for(draft.draft_id, command_id)
    digest = sha256_bytes(canonical_bytes(input_value))
    prepared = _prepared(input_value, digest)
    request = contract.make_request(
        prepared, assist_id, now.astimezone(UTC) + timedelta(seconds=DEADLINE_SECONDS),
    )
    intent = json_value({
        'schema_version': 2, 'assist_id': assist_id, 'command_id': command_id,
        'draft': input_value['draft'], 'input': input_value, 'input_hash': digest,
        'request': request, 'principal': principal,
        'profile_hash': contract.definition_hash, 'output_schema_hash': contract.output_schema_hash,
    })
    read_assist_attempt(intent, contract)
    return intent


def read_assist_attempt(intent, contract):
    try:
        if (not isinstance(intent, dict)
                or set(intent) != {'schema_version', 'assist_id', 'command_id', 'draft', 'input',
                                   'input_hash', 'request', 'principal', 'profile_hash', 'output_schema_hash'}
                or type(intent['schema_version']) is not int or intent['schema_version'] != 2):
            raise ValueError
        value = intent['input']
        content = canonical_bytes(value)
        draft = value['draft']
        request = request_from_record(intent['request'])
        principal = principal_from_record(intent['principal'])
        contract.validate_request(request)
        if (intent['draft'] != draft
                or type(draft['revision']) is not int or draft['revision'] < 1
                or principal.subject != draft['actor']
                or intent['input_hash'] != sha256_bytes(content)
                or intent['assist_id'] != assist_id_for(draft['draft_id'], intent['command_id'])
                or request.client_run_key != intent['assist_id']
                or request.input_json != content.decode('utf-8')
                or request.input_sha256 != intent['input_hash']
                or intent['profile_hash'] != contract.definition_hash
                or intent['output_schema_hash'] != contract.output_schema_hash):
            raise ValueError
        prepared = _prepared(value, intent['input_hash'])
        return AnalysisAttempt(
            intent['assist_id'], draft['project_id'], draft['stage_id'], prepared.source_key,
            principal, prepared, request, contract.definition_hash, contract.output_schema_hash,
        )
    except (KeyError, ValueError, TypeError, AttributeError, ArchiveError, AnalysisError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def read_assist_candidate(intent, candidate, contract):
    attempt = read_assist_attempt(intent, contract)
    try:
        if not isinstance(candidate, dict) or set(candidate) != {'snapshot', 'result', 'output'}:
            raise ValueError
        snapshot = snapshot_from_record(candidate['snapshot'])
        result = result_from_record(candidate['result'])
        output = contract.validate_result(attempt.prepared, attempt.request, snapshot, result)
        if canonical_bytes(output) != canonical_bytes(candidate['output']):
            raise ValueError
        return snapshot, result, output
    except (KeyError, TypeError, ValueError, ArchiveError, AnalysisError):
        raise ReportError('REPORT_AI_RESULT_INVALID') from None


def read_assist_observation(value, request, contract):
    try:
        snapshot = snapshot_from_record(value['snapshot']) if 'snapshot' in value else None
        acknowledgement = cancellation_from_record(value['cancel']) if 'cancel' in value else None
        if snapshot is not None:
            contract.validate_snapshot(request, snapshot)
        if acknowledgement is not None and snapshot is not None and acknowledgement.run_id != snapshot.run_id:
            raise ValueError
        return snapshot, acknowledgement
    except (KeyError, TypeError, ValueError, ArchiveError, AnalysisError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def result_reference(intent, snapshot, result, target_id):
    return {
        'schema_version': 2, 'assist_id': intent['assist_id'], 'run_id': snapshot.run_id,
        'profile': f'{result.profile_id}@{result.profile_version}',
        'profile_hash': intent['profile_hash'], 'input_hash': intent['input_hash'],
        'output_schema_hash': result.output_schema_sha256, 'output_hash': result.output_sha256,
        'runtime_version': result.dispatch.runtime_version, 'target_id': target_id,
    }
