from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.captures import SourceChainKey
from project_management.app.domain.report_assists import DEADLINE_SECONDS, MAX_OUTPUT_BYTES
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AiBackendTarget, AnalysisAttempt, PreparedAnalysis


def assist_id_for(draft_id, command_id):
    return str(uuid5(UUID(draft_id), 'assist:' + str(UUID(command_id))))


def make_intent(draft, command_id, input_value, contract, backend, now):
    assist_id = assist_id_for(draft.draft_id, command_id)
    content = canonical_bytes(input_value)
    digest = sha256_bytes(content)
    deadline = (now.astimezone(UTC) + timedelta(seconds=DEADLINE_SECONDS)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    request = {
        'clientRunKey': assist_id, 'scopeKey': backend.scope_key, 'profile': contract.profile_ref,
        'input': {'mediaType': 'application/json', 'content': content.decode(), 'sha256': digest},
        'logicalInputHash': {'algorithm': 'dashboard-authoring-1', 'digest': digest},
        'deadlineAt': deadline,
        'limits': {'maxInputBytes': len(content), 'maxOutputBytes': MAX_OUTPUT_BYTES,
                   'maxInputTokens': None, 'maxOutputTokens': None},
        'minimumResultRetentionSeconds': 60,
    }
    contract.validate_request(request)
    from dataclasses import asdict
    return {
        'schema_version': 1, 'assist_id': assist_id, 'command_id': command_id,
        'draft': input_value['draft'], 'input': input_value, 'input_hash': digest,
        'request': request, 'backend': asdict(backend),
        'profile_hash': contract.definition_hash, 'output_schema_hash': contract.output_schema_hash,
    }


def wire_attempt(intent, contract):
    try:
        value = intent['input']
        content = canonical_bytes(value)
        request = intent['request']
        draft = value['draft']
        if (set(intent) != {'schema_version', 'assist_id', 'command_id', 'draft', 'input', 'input_hash',
                           'request', 'backend', 'profile_hash', 'output_schema_hash'}
                or type(intent['schema_version']) is not int or intent['schema_version'] != 1
                or intent['draft'] != draft or intent['input_hash'] != sha256_bytes(content)
                or intent['assist_id'] != assist_id_for(draft['draft_id'], intent['command_id'])
                or request['clientRunKey'] != intent['assist_id']
                or request['input']['content'] != content.decode() or request['input']['sha256'] != intent['input_hash']
                or intent['profile_hash'] != contract.definition_hash
                or intent['output_schema_hash'] != contract.output_schema_hash):
            raise ValueError
        backend = AiBackendTarget(**intent['backend'])
        from project_management.services.summary_journal_reads import validate_backend
        validate_backend(backend, draft['project_id'], draft['stage_id'])
        contract.validate_request(request)
        if request['scopeKey'] != backend.scope_key or request['profile'] != contract.profile_ref:
            raise ValueError
        key = SourceChainKey('report', 'report', draft['draft_id'], draft['actor'], draft['snapshot_hash'])
        prepared = PreparedAnalysis(key, draft['draft_id'], draft['snapshot_hash'], draft['revision'], None,
                                    content.decode(), intent['input_hash'])
        return AnalysisAttempt(intent['assist_id'], draft['project_id'], draft['stage_id'], key, backend, prepared,
                               request, contract.definition_hash, contract.output_schema_hash)
    except (KeyError, ValueError, TypeError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None


def result_reference(intent, snapshot, result, target_id):
    return {
        'schema_version': 1, 'assist_id': intent['assist_id'],
        'run_id': snapshot['runId'], 'run_store_id': snapshot['runStoreId'],
        'profile': intent['request']['profile'], 'profile_hash': intent['profile_hash'],
        'input_hash': intent['input_hash'], 'output_hash': result['sha256'], 'target_id': target_id,
    }
