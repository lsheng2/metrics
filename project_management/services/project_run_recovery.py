from dataclasses import replace

from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.run_admission_values import original_operation_from_record, validate_stored_request
from project_management.app.domain.run_contracts import RunError
from project_management.storage.project_operation_discovery import (
    list_operation_locations,
    read_operation_recovery_candidate,
)


class ProjectRunRecoveryService:
    def __init__(self, run_service):
        self.run_service = run_service

    def reconcile_interrupted(self) -> tuple[str, ...]:
        root = self.run_service.archive.config.root
        limits = self.run_service.archive.config.limits
        changed = []
        for location in list_operation_locations(root):
            candidate = read_operation_recovery_candidate(root, location, limits)
            actor = ProjectActor(candidate.actor_subject)
            store = self.run_service.archive.project_operation_repository(
                actor,
                location.project_id,
                location.stage_id,
                write=True,
                initialize=False,
            )
            if not candidate.has_initial_event:
                self._repair_request_only(store, location.operation_id)
                continue
            if self._interrupt_if_unlocked(store, actor, location):
                changed.append(location.operation_id)
        return tuple(changed)

    def _repair_request_only(self, store, operation_id):
        lock = store.execution_lock()
        try:
            lock.__enter__()
        except ArchiveError as error:
            if error.code == 'ARCHIVE_BUSY':
                return False
            raise RunError('RUN_STORAGE_INVALID') from None
        except RunError as error:
            if error.code == 'RUN_BUSY':
                return False
            raise
        try:
            record = store._required_request(operation_id)
            request, policy, backend, request_hash, capture_limits = validate_stored_request(record)
            operation = original_operation_from_record(record)
            store.submit(operation, request, policy, backend, request_hash, capture_limits)
            return True
        finally:
            lock.__exit__(None, None, None)

    def _interrupt_if_unlocked(self, store, actor, location):
        lock = store.execution_lock()
        try:
            lock.__enter__()
        except ArchiveError as error:
            if error.code == 'ARCHIVE_BUSY':
                return False
            raise RunError('RUN_STORAGE_INVALID') from None
        except RunError as error:
            if error.code == 'RUN_BUSY':
                return False
            raise
        try:
            current = store.current(location.operation_id)
            if current.state not in {'capturing', 'analyzing', 'cancel_requested'}:
                return False
            candidate = replace(
                current,
                state='interrupted',
                revision=current.revision + 1,
                error_code='RUN_INTERRUPTED',
            )
            store.transition(candidate, expected_revision=current.revision)
            return True
        finally:
            lock.__exit__(None, None, None)
