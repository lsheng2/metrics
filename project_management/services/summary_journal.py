from contextlib import contextmanager
from datetime import UTC, datetime
import uuid

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.summary_contracts import (
    AcceptedSummary, AnalysisAttempt, AnalysisError, AnalysisPreparation,
)
from project_management.app.domain.summary_input import build_initial_input, unchanged_since
from project_management.services.summary_journal_reads import SummaryJournalReads, complete_source, validate_backend
from project_management.storage.admission import admit, finalize_growth


class SummaryJournal(SummaryJournalReads):
    @contextmanager
    def _analysis_repository(self, actor, project_id, stage_id, *, observation=False):
        access = self._stage_for_read if observation else self._stage_for_write
        project, stage = access(actor, project_id, stage_id)
        self._validate_root_before_lock()
        with self._locks(project, stage):
            project, stage = access(actor, project_id, stage_id)
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.verify_identity()
            if not observation and (repository.runtime / 'active-capture.json').exists():
                raise ArchiveError('ARCHIVE_BUSY')
            yield repository

    def prepare_analysis(self, actor, project_id, stage_id, source_key, contract, backend, deadline_at,
                         *, cancel_requested=None):
        validate_backend(backend, project_id, stage_id)
        with self._analysis_repository(actor, project_id, stage_id) as repository:
            chain, snapshots = self._analysis_source(repository, source_key)
            accepted, _ = self._analysis_accepted(repository, source_key)
            if accepted is not None:
                if (accepted.profile_definition_hash == contract.definition_hash
                        and unchanged_since(accepted.target_capture_id, accepted.source_hash, chain)):
                    start = next(index for index, row in enumerate(chain) if row.capture_id == accepted.target_capture_id)
                    if all(complete_source(snapshot) for snapshot in snapshots[start:]):
                        return AnalysisPreparation('no_work', accepted=accepted)
                raise AnalysisError('ANALYSIS_DELTA_REQUIRED')
            if len(chain) != 1:
                raise AnalysisError('ANALYSIS_DELTA_REQUIRED')
            profile = contract.profile_ref
            prepared = build_initial_input(project_id, repository.stage, source_key, chain[0], snapshots[0],
                                           f"{profile['key']}@{profile['revision']}")
            contract.validate_input(decode_json(prepared.input_content.encode('utf-8')))
            attempt_id = str(uuid.uuid5(uuid.UUID(stage_id), prepared.input_hash))
            intent_path = f'analysis_attempts/{attempt_id}/intent.json'
            if intent_path in repository.list_files(f'analysis_attempts/{attempt_id}'):
                existing = self._analysis_attempt(repository, attempt_id)
                if existing.backend != backend:
                    raise AnalysisError('ANALYSIS_BACKEND_MISMATCH')
                return AnalysisPreparation('ready', existing)
            self._cancel_if_requested(cancel_requested)
            self._require_no_pending_analysis(repository, source_key)
            self._analysis_deadline(deadline_at)
            request = {
                'clientRunKey': attempt_id, 'scopeKey': backend.scope_key, 'profile': contract.profile_ref,
                'input': {'mediaType': 'application/json', 'content': prepared.input_content, 'sha256': prepared.input_hash},
                'logicalInputHash': {'algorithm': 'dashboard-json-review-1', 'digest': prepared.input_hash},
                'deadlineAt': deadline_at.astimezone(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                'limits': {'maxInputBytes': len(prepared.input_content.encode('utf-8')), 'maxOutputBytes': 65536,
                           'maxInputTokens': None, 'maxOutputTokens': None},
                'minimumResultRetentionSeconds': 60,
            }
            contract.validate_request(request)
            attempt = AnalysisAttempt(attempt_id, project_id, stage_id, source_key, backend, prepared, request,
                                      contract.definition_hash, contract.output_schema_hash)
            self._append_analysis(repository, attempt_id, 'intent', attempt, intent_path)
            return AnalysisPreparation('ready', self._analysis_attempt(repository, attempt_id))

    def claim_analysis_dispatch(self, actor, project_id, stage_id, attempt_id, *, cancel_requested=None):
        with self._analysis_repository(actor, project_id, stage_id) as repository:
            attempt = self._analysis_attempt(repository, attempt_id)
            if attempt.cancel_requested:
                raise AnalysisError('ANALYSIS_CANCELED')
            self._cancel_if_requested(cancel_requested)
            self._analysis_deadline(datetime.fromisoformat(attempt.request['deadlineAt']))
            if len(self._analysis_observation_paths(repository, attempt_id)) >= 16:
                raise AnalysisError('ANALYSIS_OBSERVATION_LIMIT')
            if attempt.dispatched:
                return False
            chain, _ = self._analysis_source(repository, attempt.source_key)
            if chain[-1].capture_id != attempt.prepared.target_capture_id:
                raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
            intent = self._analysis_envelope(repository, f'analysis_attempts/{attempt_id}/intent.json', 'intent')
            payload = {'intent_hash': content_hash(intent), 'claimed_at': datetime.now(UTC).isoformat()}
            self._append_analysis(repository, attempt_id, 'dispatch', payload,
                                  f'analysis_attempts/{attempt_id}/dispatch.json')
            return True

    def request_analysis_cancel(self, actor, project_id, stage_id, attempt_id):
        with self._analysis_repository(actor, project_id, stage_id, observation=True) as repository:
            attempt = self._analysis_attempt(repository, attempt_id)
            if attempt.cancel_requested:
                return attempt
            intent = self._analysis_envelope(repository, f'analysis_attempts/{attempt_id}/intent.json', 'intent')
            payload = {'intent_hash': content_hash(intent), 'requested_at': datetime.now(UTC).isoformat()}
            self._append_analysis(repository, attempt_id, 'cancel', payload,
                                  f'analysis_attempts/{attempt_id}/cancel.json')
            return self._analysis_attempt(repository, attempt_id)

    def record_analysis_observation(self, actor, project_id, stage_id, attempt_id, observation, *, cancellation=False):
        with self._analysis_repository(actor, project_id, stage_id, observation=True) as repository:
            attempt = self._analysis_attempt(repository, attempt_id)
            if not attempt.dispatched:
                raise AnalysisError('ANALYSIS_INVALID')
            paths = self._analysis_observation_paths(repository, attempt_id)
            cancellation_recorded = any('cancel' in self._analysis_envelope(repository, path, 'observation')['payload']
                                        for path in paths)
            sequence = len(paths) + 1
            if cancellation:
                if not attempt.cancel_requested:
                    raise AnalysisError('ANALYSIS_CANCELED')
                if cancellation_recorded or sequence > 17:
                    raise AnalysisError('ANALYSIS_OBSERVATION_LIMIT')
            elif sequence > 16:
                raise AnalysisError('ANALYSIS_OBSERVATION_LIMIT')
            self._append_analysis(repository, attempt_id, 'observation', observation,
                                  f'analysis_attempts/{attempt_id}/observations/{sequence:08d}.json',
                                  event_name=f'observation:{sequence:08d}')

    def accept_analysis(self, actor, project_id, stage_id, attempt_id, snapshot, result, contract,
                        *, cancel_requested=None):
        with self._analysis_repository(actor, project_id, stage_id) as repository:
            attempt = self._analysis_attempt(repository, attempt_id)
            if not attempt.dispatched:
                raise AnalysisError('ANALYSIS_INVALID')
            candidate = contract.validate_result(attempt, snapshot, result)
            existing, record = self._analysis_accepted(repository, attempt.source_key)
            if existing is not None and record['attempt_id'] == attempt_id:
                if existing.run_result != result:
                    raise AnalysisError('ANALYSIS_RESULT_INVALID')
                return existing
            if attempt.cancel_requested:
                raise AnalysisError('ANALYSIS_CANCELED')
            self._cancel_if_requested(cancel_requested)
            self._analysis_deadline(datetime.fromisoformat(attempt.request['deadlineAt']))
            if (attempt.prepared.expected_revision != (existing.revision if existing else 0)
                    or attempt.prepared.base_summary_id != (existing.summary_id if existing else None)):
                raise AnalysisError('ANALYSIS_ACCEPTANCE_CONFLICT')
            try:
                chain, sources = self._analysis_source(repository, attempt.source_key)
            except AnalysisError:
                raise AnalysisError('ANALYSIS_ACCEPTANCE_CONFLICT') from None
            target = chain[-1]
            if (target.capture_id != attempt.prepared.target_capture_id
                    or target.source_hash != attempt.prepared.source_hash):
                raise AnalysisError('ANALYSIS_ACCEPTANCE_CONFLICT')
            profile = contract.profile_ref
            rebuilt = build_initial_input(project_id, repository.stage, attempt.source_key, target, sources[-1],
                                          f"{profile['key']}@{profile['revision']}")
            if rebuilt.input_hash != attempt.prepared.input_hash:
                raise AnalysisError('ANALYSIS_ACCEPTANCE_CONFLICT')
            accepted = AcceptedSummary(str(uuid.uuid5(uuid.UUID(attempt_id), 'accepted')), 1,
                                       target.capture_id, target.source_hash, contract.definition_hash,
                                       attempt.prepared.input_hash, candidate, decode_json(canonical_bytes(result)))
            key_hash = content_hash(attempt.source_key)
            envelope = self._analysis_event(attempt_id, 'accepted', {'summary': accepted, 'snapshot': snapshot})
            envelope.update(source_key_hash=key_hash, revision=accepted.revision)
            record_id = str(uuid.uuid5(uuid.UUID(stage_id), f'accepted:{key_hash}:{accepted.revision:08d}'))
            path = f'accepted_summaries/{key_hash}/{accepted.revision:08d}.json'
            self._commit_analysis_event(repository, record_id, 'accepted_summaries', path, envelope)
            return self._analysis_accepted(repository, attempt.source_key)[0]

    def _require_no_pending_analysis(self, repository, source_key):
        for path in repository.list_files('analysis_attempts'):
            if path.endswith('/intent.json'):
                attempt = self._analysis_attempt(repository, path.split('/')[1])
                if attempt.source_key == source_key:
                    accepted, record = self._analysis_accepted(repository, source_key)
                    if accepted is None or record['attempt_id'] != attempt.attempt_id:
                        raise AnalysisError('ANALYSIS_ATTEMPT_PENDING')

    def _analysis_deadline(self, value):
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise AnalysisError('ANALYSIS_INVALID')
        remaining = (value - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            raise AnalysisError('ANALYSIS_DEADLINE_EXPIRED')
        if remaining > 600:
            raise AnalysisError('ANALYSIS_INVALID')

    def _cancel_if_requested(self, cancel_requested):
        if cancel_requested is not None and cancel_requested():
            raise AnalysisError('ANALYSIS_CANCELED')

    def _analysis_event(self, attempt_id, kind, payload):
        return {'schema_version': 1, 'kind': kind, 'attempt_id': attempt_id, 'payload': payload}

    def _append_analysis(self, repository, attempt_id, kind, payload, path, *, event_name=None):
        envelope = self._analysis_event(attempt_id, kind, payload)
        record_id = str(uuid.uuid5(uuid.UUID(attempt_id), event_name or kind))
        self._commit_analysis_event(repository, record_id, 'analysis_attempts', path, envelope)

    def _commit_analysis_event(self, repository, record_id, namespace, path, envelope):
        payload = canonical_bytes(envelope)
        admit(self.config.root, repository.stage_root, repository.archive / namespace,
              self.config.limits, finalize_growth(1, len(payload)))
        repository.append_record(record_id, namespace, {path: payload}, expected_head=repository.head(),
                                 record_fingerprint=content_hash(envelope))
