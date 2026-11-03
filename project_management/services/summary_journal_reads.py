from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import re
from urllib.parse import urlsplit
import uuid

from project_management.app.domain.capture_values import (
    canonical_bytes, content_hash, decode_json, decode_snapshot, sha256_bytes,
)
from project_management.app.domain.captures import SourceChainKey
from project_management.app.domain.summary_contracts import (
    AcceptedSummary, AiBackendTarget, AnalysisAttempt, AnalysisError, PreparedAnalysis,
)
from project_management.app.domain.summary_input import MAX_CHAIN, complete_source
from project_management.storage.paths import validate_uuid


def validate_backend(backend, project_id, stage_id):
    try:
        parsed = urlsplit(backend.base_url)
        if (not isinstance(backend, AiBackendTarget) or parsed.scheme != 'http'
                or parsed.hostname != '127.0.0.1' or parsed.port is None
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')
                or backend.source_app_id != 'metrics-dashboard'
                or backend.scope_key != f'projects.{project_id}.stages.{stage_id}'
                or any(not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9._:-]{1,160}', value)
                       for value in (backend.run_store_id, backend.grant_revision, backend.limit_policy_revision))):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise AnalysisError('ANALYSIS_BACKEND_MISMATCH') from None


class SummaryJournalReads:
    def _analysis_envelope(self, repository, path, kind):
        value = decode_json(repository.read_file(path))
        if (not isinstance(value, dict) or type(value.get('schema_version')) is not int
                or value['schema_version'] != 1 or value.get('kind') != kind
                or not isinstance(value.get('payload'), dict)):
            raise AnalysisError('ANALYSIS_INVALID')
        validate_uuid(value.get('attempt_id'))
        return value

    def _analysis_source(self, repository, source_key):
        head = repository.head()
        manifests = self._manifests(repository, head)
        if not manifests:
            raise AnalysisError('ANALYSIS_SOURCE_INCOMPLETE')
        current = manifests[-1]
        chain = tuple(self._source_chain(repository, source_key, head))
        if len(chain) > MAX_CHAIN:
            raise AnalysisError('ANALYSIS_CHAIN_LIMIT')
        if (not chain or not current.complete or current.membership.coverage.state != 'complete'
                or current.intent.capture_id != chain[-1].capture_id
                or source_key.rule_hash != repository.stage.definition_hash
                or not any(self._source_key(current.intent, member) == source_key for member in current.membership.items)):
            raise AnalysisError('ANALYSIS_SOURCE_INCOMPLETE')
        snapshots = []
        for reference in chain:
            snapshot = decode_snapshot(repository.read_file(reference.git_path, head))
            if self._source_hash(snapshot) != reference.source_hash or snapshot.identity != reference.identity:
                raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
            snapshots.append(snapshot)
        if not complete_source(snapshots[-1]):
            raise AnalysisError('ANALYSIS_SOURCE_INCOMPLETE')
        return chain, tuple(snapshots)

    def _analysis_attempt(self, repository, attempt_id):
        validate_uuid(attempt_id)
        path = f'analysis_attempts/{attempt_id}/intent.json'
        envelope = self._analysis_envelope(repository, path, 'intent')
        try:
            data = dict(envelope['payload'])
            data['source_key'] = SourceChainKey(**data['source_key'])
            prepared = dict(data['prepared'])
            prepared['source_key'] = SourceChainKey(**prepared['source_key'])
            data['prepared'] = PreparedAnalysis(**prepared)
            data['backend'] = AiBackendTarget(**data['backend'])
            attempt = AnalysisAttempt(**data)
            validate_backend(attempt.backend, repository.project.id, repository.stage.id)
            if (attempt.attempt_id != attempt_id or envelope['attempt_id'] != attempt_id
                    or attempt.project_id != repository.project.id or attempt.stage_id != repository.stage.id
                    or attempt.source_key != attempt.prepared.source_key
                    or str(uuid.uuid5(uuid.UUID(attempt.stage_id), attempt.prepared.input_hash)) != attempt_id
                    or attempt.request['clientRunKey'] != attempt_id
                    or attempt.request['scopeKey'] != attempt.backend.scope_key
                    or attempt.request['input']['content'] != attempt.prepared.input_content
                    or attempt.request['input']['sha256'] != attempt.prepared.input_hash
                    or sha256_bytes(attempt.prepared.input_content.encode()) != attempt.prepared.input_hash):
                raise ValueError
            if self._analysis_cancel_requested(repository, attempt_id, envelope):
                attempt = replace(attempt, cancel_requested=True)
            dispatch_path = f'analysis_attempts/{attempt_id}/dispatch.json'
            if dispatch_path in repository.list_files(f'analysis_attempts/{attempt_id}'):
                dispatch = self._analysis_envelope(repository, dispatch_path, 'dispatch')
                if (dispatch['attempt_id'] != attempt_id
                        or dispatch['payload']['intent_hash'] != content_hash(envelope)):
                    raise ValueError
                attempt = replace(attempt, dispatched=True)
            return attempt
        except (KeyError, ValueError, TypeError, AttributeError):
            raise AnalysisError('ANALYSIS_INVALID') from None

    def _analysis_cancel_requested(self, repository, attempt_id, intent):
        path = f'analysis_attempts/{attempt_id}/cancel.json'
        if path not in repository.list_files(f'analysis_attempts/{attempt_id}'):
            return False
        cancel = self._analysis_envelope(repository, path, 'cancel')
        try:
            if (cancel['attempt_id'] != attempt_id
                    or cancel['payload']['intent_hash'] != content_hash(intent)
                    or type(cancel['payload']['requested_at']) is not str):
                raise ValueError
            datetime.fromisoformat(cancel['payload']['requested_at'])
            return True
        except (KeyError, ValueError, TypeError):
            raise AnalysisError('ANALYSIS_INVALID') from None

    def _analysis_accepted(self, repository, source_key):
        source_hash = content_hash(source_key)
        paths = sorted(repository.list_files(f'accepted_summaries/{source_hash}'))
        if not paths:
            return None, None
        for index, path in enumerate(paths, 1):
            if path != f'accepted_summaries/{source_hash}/{index:08d}.json':
                raise AnalysisError('ANALYSIS_INVALID')
        value = self._analysis_envelope(repository, paths[-1], 'accepted')
        try:
            summary = AcceptedSummary(**value['payload']['summary'])
            if (value.get('source_key_hash') != source_hash or value.get('revision') != len(paths)
                    or summary.revision != len(paths)
                    or summary.candidate['binding']['project_id'] != repository.project.id
                    or summary.candidate['binding']['stage_id'] != repository.stage.id
                    or summary.candidate['input_hash'] != summary.input_hash):
                raise ValueError
            return summary, value
        except (KeyError, ValueError, TypeError):
            raise AnalysisError('ANALYSIS_INVALID') from None

    def _analysis_observation_paths(self, repository, attempt_id):
        paths = sorted(repository.list_files(f'analysis_attempts/{attempt_id}/observations'))
        if any(path != f'analysis_attempts/{attempt_id}/observations/{index:08d}.json'
               for index, path in enumerate(paths, 1)):
            raise AnalysisError('ANALYSIS_INVALID')
        return paths

    def read_analysis_attempt(self, actor, project_id, stage_id, attempt_id):
        repository = self._read_repository(actor, project_id, stage_id)
        return self._analysis_attempt(repository, attempt_id)

    def read_analysis_observations(self, actor, project_id, stage_id, attempt_id):
        repository = self._read_repository(actor, project_id, stage_id)
        self._analysis_attempt(repository, attempt_id)
        observations = []
        for path in self._analysis_observation_paths(repository, attempt_id):
            envelope = self._analysis_envelope(repository, path, 'observation')
            if envelope['attempt_id'] != attempt_id:
                raise AnalysisError('ANALYSIS_INVALID')
            observations.append(deepcopy(envelope['payload']))
        return tuple(observations)
