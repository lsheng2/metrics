from dataclasses import replace
from datetime import UTC, datetime
import uuid

from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectActor, ProjectError
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.run_contracts import ItemRunResult, RunError, RunOperation, RunPolicy
from project_management.app.domain.run_admission_values import (
    original_operation_from_record,
    validate_stored_request,
)
from project_management.app.domain.run_values import (
    NONTERMINAL_STATES,
    TERMINAL_STATES,
    capture_id,
    deadline_from,
    draft_command_id,
    normalized_request,
    normalize_template,
    operation_id,
    parse_instant,
    policy_hash,
    request_hash,
    utc_instant_millis,
    validate_policy,
    validate_request,
    validate_uuid_text,
)
from project_management.services.project_run_recovery import ProjectRunRecoveryService
from provider_sync.app.api.access_contracts import AccessContext, CaptureLimits


class ProjectRunService:
    def __init__(self, project_api, archive, capture_service, analysis_service,
                 draft_service, backend_resolver, *, policy=None, capture_limits=None,
                 clock=None, notifier=None):
        self.project_api = project_api
        self.archive = archive
        self.capture_service = capture_service
        self.analysis_service = analysis_service
        self.draft_service = draft_service
        self.backend_resolver = backend_resolver
        self.policy = validate_policy(policy)
        self.capture_limits = capture_limits or CaptureLimits()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.notifier = notifier

    def submit(self, actor, project_id, stage_id, request):
        try:
            request = validate_request(request)
            template = normalize_template(self.draft_service.renderer, request.template)
            request = normalized_request(request, template)
            request_hash_value = request_hash(request)
            op_id = operation_id(stage_id, request.command_id)
            replay = self._submit_replay(actor, project_id, stage_id, op_id, request_hash_value)
            if replay is not None:
                return replay
            if self.notifier is None:
                raise RunError('RUN_UNAVAILABLE')
            project, stage = self._writable_stage(actor, project_id, stage_id)
            if request.expected_stage_hash != stage.definition_hash:
                raise RunError('RUN_SOURCE_CHANGED')
            store = self._store(actor, project_id, stage_id, write=True, initialize=True)
            try:
                record = store._request_record(op_id)
            except RunError:
                raise
            if record is not None:
                stored_request, stored_policy, backend, stored_hash, stored_capture_limits = validate_stored_request(record)
                if stored_hash != request_hash_value:
                    raise RunError('RUN_COMMAND_CONFLICT')
                operation = self._operation_from_record(record)
                operation = store.submit(operation, stored_request, stored_policy, backend, stored_hash, stored_capture_limits)
                if operation.state in NONTERMINAL_STATES:
                    self._notify(actor, project_id, stage_id, operation.operation_id)
                return operation
            backend = self.backend_resolver(actor, project_id, stage_id)
            created_at = utc_instant_millis(self.clock())
            policy = self.policy
            op_id = operation_id(stage.id, request.command_id)
            operation = RunOperation(
                operation_id=op_id,
                command_id=request.command_id,
                project_id=project.id,
                stage_id=stage.id,
                actor_subject=actor.subject,
                stage_hash=stage.definition_hash,
                policy_hash=policy_hash(policy),
                created_at=created_at,
                deadline_at=deadline_from(created_at, policy),
                capture_id=capture_id(op_id),
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
                execution_mode='synthetic',
            )
            operation = store.submit(operation, request, policy, backend, request_hash_value, self.capture_limits)
            self._notify(actor, project_id, stage_id, operation.operation_id)
            return operation
        except RunError:
            raise
        except (ArchiveError, ProjectError) as error:
            raise self._run_error(error) from None

    def get(self, actor, project_id, stage_id, operation_id_value):
        try:
            validate_uuid_text(operation_id_value)
            store = self._store(actor, project_id, stage_id)
            operation = store.current(operation_id_value)
            if operation.actor_subject != actor.subject:
                raise RunError('RUN_NOT_FOUND')
            return operation
        except RunError:
            raise
        except (ArchiveError, ProjectError) as error:
            raise self._run_error(error, missing_as_not_found=True) from None

    def list(self, actor, project_id, stage_id, *, limit=20):
        try:
            store = self._store(actor, project_id, stage_id)
            return tuple(row for row in store.list(limit=limit) if row.actor_subject == actor.subject)
        except RunError:
            raise
        except (ArchiveError, ProjectError) as error:
            raise self._run_error(error, missing_as_not_found=True) from None

    def cancel(self, actor, project_id, stage_id, operation_id_value, *, expected_revision):
        operation = self.get(actor, project_id, stage_id, operation_id_value)
        if operation.state in TERMINAL_STATES:
            return operation
        state = 'canceled' if operation.state == 'queued' else 'cancel_requested'
        candidate = replace(
            operation,
            state=state,
            revision=operation.revision + 1,
            cancel_requested=True,
            error_code=None,
        )
        store = self._store(actor, project_id, stage_id, write=True)
        updated = store.transition(candidate, expected_revision=expected_revision)
        self._record_analysis_cancel_intents(actor, project_id, stage_id, updated)
        return updated

    def resume(self, actor, project_id, stage_id, operation_id_value, *, expected_revision):
        operation = self.get(actor, project_id, stage_id, operation_id_value)
        if operation.state in TERMINAL_STATES:
            return operation
        if type(expected_revision) is not int:
            raise RunError('RUN_INVALID')
        if operation.revision != expected_revision:
            raise RunError('RUN_REVISION_CONFLICT')
        if operation.state == 'interrupted' and not operation.cancel_requested:
            candidate = replace(operation, state='queued', revision=operation.revision + 1)
            operation = self._store(actor, project_id, stage_id, write=True).transition(
                candidate,
                expected_revision=expected_revision,
            )
        self._notify(actor, project_id, stage_id, operation.operation_id)
        return operation

    def operation_request(self, actor, project_id, stage_id, operation_id_value):
        store = self._store(actor, project_id, stage_id)
        request, policy, backend, request_hash_value, capture_limits = store.request_record(operation_id_value)
        return request, policy, backend, request_hash_value, capture_limits

    def capture_context(self, operation):
        return AccessContext(
            ProjectActor(operation.actor_subject),
            operation.project_id,
            operation.stage_id,
            operation.capture_id,
            operation.operation_id,
            self.operation_deadline(operation),
            self._capture_limits_for(operation),
        )

    def operation_deadline(self, operation):
        return parse_instant(operation.deadline_at)

    def transition(self, actor, project_id, stage_id, operation_id_value, updater):
        current = self.get(actor, project_id, stage_id, operation_id_value)
        candidate = updater(current)
        return self._store(actor, project_id, stage_id, write=True).transition(
            candidate,
            expected_revision=current.revision,
        )

    def write_draft_selection(self, actor, project_id, stage_id, operation_id_value, payload):
        self._store(actor, project_id, stage_id, write=True).write_draft_selection(operation_id_value, payload)

    def execution_lock(self, actor, project_id, stage_id):
        return self._store(actor, project_id, stage_id).execution_lock()

    def reconcile_interrupted(self):
        return ProjectRunRecoveryService(self).reconcile_interrupted()

    def _operation_from_record(self, record):
        return original_operation_from_record(record)

    def _submit_replay(self, actor, project_id, stage_id, operation_id_value, request_hash_value):
        try:
            store = self._store(actor, project_id, stage_id, write=False, initialize=False)
            record = store._request_record(operation_id_value)
            if record is None:
                return None
            stored_request, stored_policy, backend, stored_hash, stored_capture_limits = validate_stored_request(record)
            if stored_hash != request_hash_value:
                raise RunError('RUN_COMMAND_CONFLICT')
            operation = self._operation_from_record(record)
            return store.submit(operation, stored_request, stored_policy, backend, stored_hash, stored_capture_limits)
        except RunError as error:
            if error.code in {'RUN_NOT_FOUND', 'RUN_UNAVAILABLE'}:
                return None
            raise

    def _capture_limits_for(self, operation):
        _, _, _, _, values = self.operation_request(
            ProjectActor(operation.actor_subject),
            operation.project_id,
            operation.stage_id,
            operation.operation_id,
        )
        return CaptureLimits(**values)

    def _record_analysis_cancel_intents(self, actor, project_id, stage_id, operation):
        for result in operation.item_results:
            if result.attempt_id is None or result.state in {'accepted', 'no_work', 'canceled'}:
                continue
            try:
                self.archive.request_analysis_cancel(actor, project_id, stage_id, result.attempt_id)
            except Exception:
                raise RunError('RUN_STORAGE_INVALID') from None

    def _store(self, actor, project_id, stage_id, *, write=False, initialize=False):
        try:
            return self.archive.project_operation_repository(
                actor,
                project_id,
                stage_id,
                write=write,
                initialize=initialize,
            )
        except (ArchiveError, ProjectError) as error:
            raise self._run_error(error, missing_as_not_found=not write) from None

    def _writable_stage(self, actor, project_id, stage_id):
        detail = self.project_api.get_project(actor, project_id)
        for stage in detail.stages:
            if stage.id == stage_id:
                if detail.project.archived or stage.source_status != 'current':
                    raise RunError('RUN_SOURCE_CHANGED')
                return detail.project, stage
        raise RunError('RUN_NOT_FOUND')

    def _notify(self, actor, project_id, stage_id, operation_id_value):
        if self.notifier is None:
            return
        try:
            self.notifier(actor, project_id, stage_id, operation_id_value)
        except Exception:
            return

    def _run_error(self, error, *, missing_as_not_found=False):
        code = getattr(error, 'code', '')
        if isinstance(error, ProjectError):
            if code == 'PROJECT_NOT_FOUND':
                return RunError('RUN_NOT_FOUND')
            if code in {'PROJECT_ARCHIVED', 'SOURCE_CHANGED', 'SOURCE_UNAVAILABLE'}:
                return RunError('RUN_SOURCE_CHANGED')
        if code == 'ARCHIVE_BUSY':
            return RunError('RUN_BUSY')
        if code == 'ARCHIVE_QUOTA_EXCEEDED':
            return RunError('RUN_LIMIT')
        if code in {'ARCHIVE_ROOT_UNCONFIGURED', 'ARCHIVE_CONFIG_INVALID'}:
            return RunError('RUN_UNAVAILABLE')
        if code == 'ARCHIVE_DEADLINE_EXPIRED':
            return RunError('RUN_DEADLINE_EXPIRED')
        if code == 'ARCHIVE_STORAGE_UNAVAILABLE':
            return RunError('RUN_STORAGE_UNAVAILABLE')
        if code == 'ARCHIVE_RAW_PAGE_MISSING' and missing_as_not_found:
            return RunError('RUN_NOT_FOUND')
        if code in {'ARCHIVE_MANIFEST_INVALID', 'ARCHIVE_IDENTITY_MISMATCH', 'UNSAFE_PATH'}:
            return RunError('RUN_STORAGE_INVALID')
        return RunError('RUN_INVALID')


def replace_item(operation, source_key_hash, item):
    values = []
    replaced = False
    for row in operation.item_results:
        if row.source_key_hash == source_key_hash:
            values.append(item)
            replaced = True
        else:
            values.append(row)
    if not replaced:
        values.append(item)
    return replace(operation, item_results=tuple(values))
