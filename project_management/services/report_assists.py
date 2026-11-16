from datetime import UTC, datetime

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_assists import MAX_OBSERVATIONS, AssistStatus, available_targets, build_assist_input
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.task_run_observations import execution_is_settled, submit_was_rejected
from project_management.app.domain.task_runs import TaskPrincipal, TaskRunCancellation, TaskRunError
from project_management.services.report_assist_records import (
    assist_id_for, make_intent, read_assist_attempt, read_assist_candidate, read_assist_observation,
)
from project_management.storage.report_assists import ReportAssistStore


class ReportAssistService:
    assist_id_for = staticmethod(assist_id_for)

    def __init__(self, draft_service, contract, *, task_run_port=None, principal_resolver=None, clock=None):
        self.drafts = draft_service
        self.archive = draft_service.archive
        self.contract = contract
        self.task_run_port = task_run_port
        self.principal_resolver = principal_resolver
        self.clock = clock or (lambda: datetime.now(UTC))

    def _principal(self, actor):
        if self.task_run_port is None or self.principal_resolver is None:
            raise ReportError('REPORT_AI_UNAVAILABLE')
        principal = self.principal_resolver(actor)
        if not isinstance(principal, TaskPrincipal) or principal.subject != actor.subject:
            raise ReportError('REPORT_AI_UNAVAILABLE')
        return principal

    def submit(self, actor, project_id, stage_id, draft_id, *, command_id, expected_revision,
               expected_revision_hash, target_ids, instruction):
        draft_id, command_id = self.drafts._uuid(draft_id), self.drafts._uuid(command_id)
        assist_id = assist_id_for(draft_id, command_id)
        args = (actor, project_id, stage_id, draft_id, assist_id)
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repo:
            store = ReportAssistStore(repo)
            current = self.drafts._store(repo).read_draft(draft_id)
            original = store.read(assist_id, 'intent')
            if original is not None:
                read_assist_attempt(original, self.contract)
                self._validate_identity(original, *args)
                value = original['input']
                if (value['draft']['revision'] != expected_revision or value['draft']['revision_hash'] != expected_revision_hash
                        or value['instruction'] != instruction
                        or sorted(target_ids) != sorted(item['target_id'] for item in value['targets'])):
                    raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')
                if store.read(assist_id, 'dispatch') is not None or store.read(assist_id, 'cancel') is not None:
                    return self._status(store, assist_id, draft_id)
            if type(expected_revision) is not int:
                raise ReportError('REPORT_INVALID')
            self.drafts._verify_authored_current(current, expected_revision, expected_revision_hash)
            value = original['input'] if original is not None else build_assist_input(current, target_ids, instruction)
            principal = self._principal(actor)
            active = store.active(draft_id)
            if active and active != assist_id and self._status(store, active, draft_id).state in {'prepared', 'observing', 'unknown', 'cancel_requested'}:
                raise ReportError('REPORT_AI_BUSY')
            intent = original or make_intent(current, command_id, value, self.contract, principal, self.clock())
            attempt = read_assist_attempt(intent, self.contract)
            if attempt.principal != principal:
                raise ReportError('REPORT_AI_UNAVAILABLE')
            if attempt.request.deadline_at <= self.clock():
                raise ReportError('REPORT_AI_EXPIRED')
            store.write(assist_id, 'intent', intent)
            store.set_active(draft_id, assist_id)
            store.write(assist_id, 'dispatch', {'input_hash': intent['input_hash']})
        return self._exchange(args, intent, 'submit')

    def observe(self, actor, project_id, stage_id, draft_id, assist_id):
        args = (actor, project_id, stage_id, draft_id, assist_id)
        intent = self._read_intent(*args)
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repo:
            store = ReportAssistStore(repo)
            status = self._status(store, assist_id, draft_id)
            if status.state in {'candidate_ready', 'insufficient_evidence', 'failed', 'canceled', 'prepared'}:
                return status
        operation = 'settle_cancel' if status.state == 'cancel_requested' else 'observe'
        return self._exchange(args, intent, operation)

    def candidate(self, actor, project_id, stage_id, draft_id, assist_id):
        intent = self._read_intent(actor, project_id, stage_id, draft_id, assist_id)
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repo:
            store = ReportAssistStore(repo)
            if store.read(assist_id, 'cancel') is not None:
                raise ReportError('REPORT_AI_CANCELED')
            draft = self.drafts._store(repo).read_draft(draft_id)
            self.drafts._verify_authored_current(draft, intent['draft']['revision'], intent['draft']['revision_hash'])
            value = store.read(assist_id, 'candidate')
            if value is None:
                raise ReportError('REPORT_AI_UNAVAILABLE')
            return read_assist_candidate(intent, value, self.contract)[2]

    def cancel(self, actor, project_id, stage_id, draft_id, assist_id, *, command_id):
        self.drafts._uuid(command_id)
        args = (actor, project_id, stage_id, draft_id, assist_id)
        intent = self._read_intent(*args)
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repo:
            store = ReportAssistStore(repo)
            if store.read(assist_id, 'cancel') is not None:
                return self._status(store, assist_id, draft_id)
            store.write(assist_id, 'cancel', {'command_id': command_id})
            status = self._status(store, assist_id, draft_id)
            if status.state == 'canceled':
                return status
        return self._exchange(args, intent, 'cancel')

    def _read_intent(self, actor, project_id, stage_id, draft_id, assist_id):
        self.drafts._uuid(draft_id)
        self.drafts._uuid(assist_id)
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repo:
            value = ReportAssistStore(repo).read(assist_id, 'intent')
            if value is None:
                raise ReportError('REPORT_NOT_FOUND')
            read_assist_attempt(value, self.contract)
            self._validate_identity(value, actor, project_id, stage_id, draft_id, assist_id)
            return value

    def describe(self, actor, project_id, stage_id, draft_id):
        self.drafts._uuid(draft_id)
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repo:
            draft = self.drafts._store(repo).read_draft(draft_id)
            store = ReportAssistStore(repo)
            latest = store.active(draft_id)
            return {
                'available': self.principal_resolver is not None and self.task_run_port is not None,
                'targets': [{'target_id': item.target_id, 'target': item.target} for item in available_targets(draft)],
                'latest': None if latest is None else self._status(store, latest, draft_id),
            }

    def _validate_identity(self, value, actor, project_id, stage_id, draft_id, assist_id):
        draft = value['draft']
        if (draft['actor'], draft['project_id'], draft['stage_id'], draft['draft_id'], value['assist_id']) != (
                actor.subject, project_id, stage_id, draft_id, assist_id):
            raise ReportError('REPORT_NOT_FOUND')

    def _status(self, store, assist_id, draft_id):
        intent = store.read(assist_id, 'intent')
        attempt = read_assist_attempt(intent, self.contract)
        if (intent['draft']['draft_id'] != draft_id or attempt.project_id != store.repository.project.id
                or attempt.stage_id != store.repository.stage.id
                or intent['draft']['actor'] != store.repository.owner_subject):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        observations = store.observations(assist_id)
        last = observations[-1] if observations else {}
        settled = False
        failed = None
        run_id = None
        for observation in observations:
            snapshot, ack = read_assist_observation(observation, attempt.request, self.contract)
            proof = submit_was_rejected(observation)
            if snapshot is not None:
                if run_id is not None and run_id != snapshot.run_id:
                    raise ReportError('REPORT_ARTIFACT_INVALID')
                run_id = snapshot.run_id
                proof = execution_is_settled(snapshot)
            if ack is not None:
                if run_id is None or ack.run_id != run_id:
                    raise ReportError('REPORT_ARTIFACT_INVALID')
            settled = settled or proof
            if observation['state'] == 'failed':
                if not proof:
                    raise ReportError('REPORT_ARTIFACT_INVALID')
                failed = observation
        candidate = store.read(assist_id, 'candidate')
        if candidate is not None:
            output = read_assist_candidate(intent, candidate, self.contract)[2]
            settled = True
        exhausted = store.exchange_count(assist_id) >= MAX_OBSERVATIONS
        expired = attempt.request.deadline_at <= self.clock()
        error = 'REPORT_AI_LIMIT' if exhausted else 'REPORT_AI_EXPIRED' if expired else last.get('error_code')
        if store.read(assist_id, 'cancel') is not None:
            stopped = settled or store.read(assist_id, 'dispatch') is None
            return AssistStatus(assist_id, 'canceled' if stopped else 'cancel_requested', error_code=None if stopped else error)
        if candidate is not None:
            filled = any(item['status'] == 'filled' for item in output['targets'])
            return AssistStatus(assist_id, 'candidate_ready' if filled else 'insufficient_evidence')
        if failed is not None:
            return AssistStatus(assist_id, 'failed', error_code=failed.get('error_code'))
        if exhausted or expired:
            return AssistStatus(assist_id, 'failed' if settled else 'unknown', error_code=error)
        fallback = 'unknown' if store.read(assist_id, 'dispatch') is not None else 'prepared'
        return AssistStatus(assist_id, last.get('state', fallback), error_code=last.get('error_code'))

    def _exchange(self, args, intent, operation):
        actor, project_id, stage_id, draft_id, assist_id = args
        attempt = read_assist_attempt(intent, self.contract)
        principal = self._principal(actor)
        if principal != attempt.principal:
            raise ReportError('REPORT_AI_UNAVAILABLE')
        remaining = (attempt.request.deadline_at - self.clock()).total_seconds()
        known = acknowledgement = None
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repo:
            store = ReportAssistStore(repo)
            if remaining <= 0 and operation not in {'cancel', 'settle_cancel'}:
                return self._status(store, assist_id, draft_id)
            for previous in store.observations(assist_id):
                observed, prior_ack = read_assist_observation(previous, attempt.request, self.contract)
                if observed is not None:
                    if known is not None and observed.run_id != known.run_id:
                        raise ReportError('REPORT_ARTIFACT_INVALID')
                    known = observed
                if prior_ack is not None:
                    acknowledgement = prior_ack
            # Reserve before port I/O so concurrent observers cannot refund the bound.
            if not store.claim_exchange(assist_id, operation):
                return self._status(store, assist_id, draft_id)
        observation = {'operation': operation}
        settled = False
        try:
            if operation == 'submit':
                snapshot = self.task_run_port.start(principal, attempt.request)
            elif known is None:
                snapshot = self.task_run_port.lookup(principal, attempt.request)
            else:
                snapshot = self.task_run_port.get(principal, attempt.request, known.run_id)
            if snapshot is None:
                state = 'cancel_requested' if operation in {'cancel', 'settle_cancel'} else 'unknown'
                return self._record(args, {**observation, 'state': state})
            self.contract.validate_snapshot(attempt.request, snapshot)
            observation['snapshot'] = snapshot
            settled = execution_is_settled(snapshot)
            if operation in {'cancel', 'settle_cancel'}:
                if not settled and acknowledgement is None:
                    acknowledgement = self.task_run_port.cancel(principal, snapshot.run_id)
                    if (not isinstance(acknowledgement, TaskRunCancellation)
                            or acknowledgement.run_id != snapshot.run_id):
                        raise ReportError('REPORT_AI_RESULT_INVALID')
                    observation['cancel'] = acknowledgement
                    snapshot = self.task_run_port.get(principal, attempt.request, snapshot.run_id)
                    self.contract.validate_snapshot(attempt.request, snapshot)
                    observation['snapshot'] = snapshot
                    settled = execution_is_settled(snapshot)
                return self._record(args, {**observation, 'state': 'canceled' if settled else 'cancel_requested'})
            state = self._snapshot_state(snapshot)
            if snapshot.status != 'succeeded' or not settled:
                return self._record(args, {**observation, 'state': state})
            result = self.task_run_port.result(principal, attempt.request, snapshot.run_id)
            observation['result'] = result
            output = self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)
            return self._publish_candidate(args, intent, snapshot, result, output, observation)
        except TaskRunError as error:
            observation.update(retry=error.retry, code=error.runtime_code or error.code)
            rejected = submit_was_rejected(observation) and not settled
            state = 'failed' if rejected else 'observing' if settled else 'unknown'
            return self._record(args, {**observation, 'state': state, 'error_code': 'REPORT_AI_UNAVAILABLE'})
        except (AnalysisError, ReportError) as error:
            if isinstance(error, ReportError) and error.code in {'REPORT_STORAGE_UNAVAILABLE', 'REPORT_ARTIFACT_INVALID', 'REPORT_LIMIT'}:
                raise
            return self._record(args, {**observation, 'state': 'failed' if settled else 'unknown',
                                       'error_code': getattr(error, 'code', 'REPORT_AI_RESULT_INVALID')})

    def _record(self, args, observation):
        actor, project_id, stage_id, draft_id, assist_id = args
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repo:
            store = ReportAssistStore(repo)
            store.append(assist_id, observation)
            return self._status(store, assist_id, draft_id)

    def _publish_candidate(self, args, intent, snapshot, result, output, observation):
        actor, project_id, stage_id, draft_id, assist_id = args
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repo:
            store = ReportAssistStore(repo)
            if store.read(assist_id, 'cancel') is not None:
                store.append(assist_id, {**observation, 'state': 'canceled'})
                return self._status(store, assist_id, draft_id)
            if any(item['state'] == 'failed' for item in store.observations(assist_id)):
                return self._status(store, assist_id, draft_id)
            draft = self.drafts._store(repo).read_draft(draft_id)
            self.drafts._verify_authored_current(draft, intent['draft']['revision'], intent['draft']['revision_hash'])
            if store.read(assist_id, 'candidate') is None:
                store.write(assist_id, 'candidate', {'snapshot': snapshot, 'result': result, 'output': output})
            store.append(assist_id, {**observation, 'state': 'candidate_ready'})
            return self._status(store, assist_id, draft_id)

    def _snapshot_state(self, snapshot):
        if snapshot.status == 'indeterminate' or snapshot.dispatch.uncertainty == 'unknown':
            return 'unknown'
        if snapshot.status in {'failed', 'timed_out', 'canceled'} and execution_is_settled(snapshot):
            return 'failed'
        return 'observing'
