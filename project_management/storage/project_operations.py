from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import re

from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.run_contracts import RunError, RunOperation
from project_management.app.domain.run_admission_values import (
    original_operation_from_record,
    stored_request_payload,
    validate_stored_request,
)
from project_management.app.domain.run_values import (
    NONTERMINAL_STATES,
    TERMINAL_STATES,
    decode_mapping,
    operation_from_mapping,
    validate_transition,
    validate_uuid_text,
)
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.locks import CombinedLocks, exclusive_lock
from project_management.storage.paths import controlled_path, inspect_components, read_bytes, safe_relative_path, write_bytes


REQUEST_LIMIT = 1024 * 1024
MAX_STAGE_OPERATIONS = 1000
MAX_GLOBAL_SCAN = 10000
MAX_EVENTS = 1024


class ProjectOperationRepository:
    def __init__(self, root: Path, stage_root: Path, runtime: Path, root_lock: Path, stage_lock: Path, limits):
        self.root = Path(root)
        self.stage_root = Path(stage_root)
        self.runtime = Path(runtime)
        self.root_lock = Path(root_lock)
        self.stage_lock = Path(stage_lock)
        self.limits = limits
        self.operations = self.runtime / 'operations'

    def submit(self, operation, request, policy, backend, request_hash, capture_limits):
        record = stored_request_payload(operation, request, policy, backend, request_hash, capture_limits)
        with self._locks():
            existing = self._request_record(operation.operation_id)
            if existing is not None:
                _, _, _, existing_hash, _ = validate_stored_request(existing)
                if existing_hash != request_hash:
                    raise RunError('RUN_COMMAND_CONFLICT')
                if not self._event_paths(operation.operation_id):
                    self._admit_projection(operation, request_hash, existing['admission_hash'], None)
                    self._append_event(operation, request_hash, existing['admission_hash'], previous_event_hash=None)
                    self._write_state(operation, self._event_hash(operation.operation_id, operation.revision))
                    self._write_active(operation)
                    return operation
                return self.current(operation.operation_id)
            self._enforce_stage_operation_limit()
            self._enforce_pending_capacity(policy.max_queued_operations)
            self._enforce_stage_slot()
            self._admit_write(operation.operation_id, len(canonical_bytes(record)) + len(canonical_bytes(operation)) + 64 * 1024, 8)
            self._write_request(operation.operation_id, record)
            self._admit_projection(operation, request_hash, record['admission_hash'], None)
            self._append_event(operation, request_hash, record['admission_hash'], previous_event_hash=None)
            self._write_state(operation, self._event_hash(operation.operation_id, operation.revision))
            self._write_active(operation)
            return operation

    def current(self, operation_id):
        validate_uuid_text(operation_id)
        record = self._required_request(operation_id)
        _, _, _, request_hash, _ = validate_stored_request(record)
        events = self._events(operation_id, request_hash)
        if not events:
            raise RunError('RUN_STORAGE_INVALID')
        return events[-1][0]

    def request_record(self, operation_id):
        record = self._required_request(operation_id)
        request, policy, backend, request_hash, capture_limits = validate_stored_request(record)
        return request, policy, backend, request_hash, capture_limits

    def list(self, *, limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise RunError('RUN_INVALID')
        operations = []
        for path in self._operation_dirs():
            try:
                operations.append(self.current(path.name))
            except RunError as error:
                if error.code == 'RUN_STORAGE_INVALID':
                    raise
        operations.sort(key=lambda row: (row.created_at, row.operation_id), reverse=True)
        return tuple(operations[:limit])

    def transition(self, candidate: RunOperation, *, expected_revision: int):
        if type(expected_revision) is not int:
            raise RunError('RUN_INVALID')
        with self._locks():
            current = self.current(candidate.operation_id)
            if current.revision != expected_revision:
                raise RunError('RUN_REVISION_CONFLICT')
            validate_transition(current, candidate)
            request_record = self._required_request(candidate.operation_id)
            request_hash = request_record['request_hash']
            previous_hash = self._event_hash(candidate.operation_id, current.revision)
            self._admit_projection(candidate, request_hash, request_record['admission_hash'], previous_hash)
            self._append_event(candidate, request_hash, request_record['admission_hash'], previous_event_hash=previous_hash)
            event_hash = self._event_hash(candidate.operation_id, candidate.revision)
            self._write_state(candidate, event_hash)
            if candidate.state in NONTERMINAL_STATES:
                self._write_active(candidate)
            else:
                self._clear_active(candidate.operation_id)
            return candidate

    def write_draft_selection(self, operation_id, payload):
        validate_uuid_text(operation_id)
        root = self._operation_root(operation_id)
        try:
            with self._locks():
                self._admit_write(operation_id, len(canonical_bytes(payload)) + 8192, 2)
                write_bytes(root, 'draft-selection.json', canonical_bytes(payload), immutable=True,
                            conflict_code='ARCHIVE_CHAIN_CONFLICT')
        except ArchiveError as error:
            raise self._run_error(error) from None

    def execution_lock(self):
        try:
            return exclusive_lock(self.operations / 'execution.lock')
        except ArchiveError as error:
            raise self._run_error(error) from None

    def _locks(self):
        return CombinedLocks(self.root_lock, self.stage_lock)

    def _write_request(self, operation_id, record):
        try:
            self._admit_write(operation_id, len(canonical_bytes(record)) + 8192, 2)
            write_bytes(self._operation_root(operation_id), 'request.json', canonical_bytes(record), immutable=True)
        except ArchiveError as error:
            raise self._run_error(error) from None

    def _required_request(self, operation_id):
        record = self._request_record(operation_id)
        if record is None:
            raise RunError('RUN_NOT_FOUND')
        return record

    def _request_record(self, operation_id):
        root = self._operation_root(operation_id)
        if not (root / 'request.json').exists():
            return None
        try:
            return decode_mapping(read_bytes(root, 'request.json', limit=REQUEST_LIMIT))
        except (ArchiveError, RunError) as error:
            if isinstance(error, RunError):
                raise
            raise self._run_error(error) from None

    def _append_event(self, operation, request_hash, admission_hash, *, previous_event_hash):
        if operation.revision > MAX_EVENTS:
            raise RunError('RUN_LIMIT')
        event = {
            'schema_version': 1,
            'operation_id': operation.operation_id,
            'request_hash': request_hash,
            'admission_hash': admission_hash,
            'sequence': operation.revision,
            'previous_event_hash': previous_event_hash,
            'recorded_at': operation.created_at if operation.revision == 1 else datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'operation': operation,
        }
        path = f'events/{operation.revision:08d}.json'
        try:
            self._admit_write(operation.operation_id, len(canonical_bytes(event)) + 8192, 2)
            write_bytes(self._operation_root(operation.operation_id), path, canonical_bytes(event), immutable=True,
                        conflict_code='ARCHIVE_CHAIN_CONFLICT')
        except ArchiveError as error:
            raise self._run_error(error) from None

    def _admit_projection(self, operation, request_hash, admission_hash, previous_event_hash):
        event = {
            'schema_version': 1,
            'operation_id': operation.operation_id,
            'request_hash': request_hash,
            'admission_hash': admission_hash,
            'sequence': operation.revision,
            'previous_event_hash': previous_event_hash,
            'recorded_at': operation.created_at if operation.revision == 1 else datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'operation': operation,
        }
        state = {'schema_version': 1, 'operation': operation, 'event_hash': 'a' * 64}
        active = {'schema_version': 1, 'operation_id': operation.operation_id,
                  'state': operation.state, 'revision': operation.revision}
        size = len(canonical_bytes(event)) + len(canonical_bytes(state)) + 16384
        files = 4
        if operation.state in NONTERMINAL_STATES:
            size += len(canonical_bytes(active)) + 8192
            files += 2
        self._admit_write(operation.operation_id, size, files)

    def _events(self, operation_id, request_hash):
        previous_hash = None
        events = []
        paths = self._event_paths(operation_id)
        if len(paths) > MAX_EVENTS:
            raise RunError('RUN_LIMIT')
        for expected, path in enumerate(paths, 1):
            if path.name != f'{expected:08d}.json':
                raise RunError('RUN_STORAGE_INVALID')
            event = self._read_event(operation_id, path)
            if (
                event.get('schema_version') != 1
                or event.get('operation_id') != operation_id
                or event.get('request_hash') != request_hash
                or event.get('admission_hash') != self._required_request(operation_id)['admission_hash']
                or event.get('sequence') != expected
                or event.get('previous_event_hash') != previous_hash
            ):
                raise RunError('RUN_STORAGE_INVALID')
            operation = operation_from_mapping(event['operation'])
            if operation.revision != expected:
                raise RunError('RUN_STORAGE_INVALID')
            if expected == 1:
                if operation != original_operation_from_record(self._required_request(operation_id)):
                    raise RunError('RUN_STORAGE_INVALID')
            else:
                try:
                    validate_transition(events[-1][0], operation)
                except RunError:
                    raise RunError('RUN_STORAGE_INVALID') from None
            event_hash = content_hash(event)
            events.append((operation, event_hash))
            previous_hash = event_hash
        return events

    def _read_event(self, operation_id, path):
        try:
            event = decode_mapping(read_bytes(self._operation_root(operation_id), f'events/{path.name}', limit=REQUEST_LIMIT))
        except ArchiveError as error:
            raise self._run_error(error) from None
        expected = {'schema_version', 'operation_id', 'request_hash', 'admission_hash', 'sequence', 'previous_event_hash', 'recorded_at', 'operation'}
        if set(event) != expected:
            raise RunError('RUN_STORAGE_INVALID')
        return event

    def _event_hash(self, operation_id, revision):
        path = self._operation_root(operation_id) / 'events' / f'{revision:08d}.json'
        if not path.exists():
            raise RunError('RUN_STORAGE_INVALID')
        return content_hash(self._read_event(operation_id, path))

    def _event_paths(self, operation_id):
        events = self._operation_root(operation_id) / 'events'
        if not events.exists():
            return ()
        try:
            inspect_components(events)
            paths = []
            for path in events.iterdir():
                if path.name.startswith('.'):
                    continue
                if path.is_file():
                    paths.append(path)
            return tuple(sorted(paths))
        except OSError:
            raise RunError('RUN_STORAGE_UNAVAILABLE') from None

    def _write_state(self, operation, event_hash):
        payload = {'schema_version': 1, 'operation': operation, 'event_hash': event_hash}
        try:
            self._admit_write(operation.operation_id, len(canonical_bytes(payload)) + 8192, 2)
            write_bytes(self._operation_root(operation.operation_id), 'state.json', canonical_bytes(payload))
        except ArchiveError as error:
            raise self._run_error(error) from None

    def _write_active(self, operation):
        payload = {
            'schema_version': 1,
            'operation_id': operation.operation_id,
            'state': operation.state,
            'revision': operation.revision,
        }
        try:
            self._admit_write(operation.operation_id, len(canonical_bytes(payload)) + 8192, 2)
            write_bytes(self.operations, 'active.json', canonical_bytes(payload))
        except ArchiveError as error:
            raise self._run_error(error) from None

    def _clear_active(self, operation_id):
        active = self.operations / 'active.json'
        if not active.exists():
            return
        try:
            payload = decode_mapping(read_bytes(self.operations, 'active.json', limit=REQUEST_LIMIT))
            if payload.get('operation_id') == operation_id:
                active.unlink()
        except OSError:
            raise RunError('RUN_STORAGE_UNAVAILABLE') from None
        except (ArchiveError, RunError):
            return

    def _enforce_stage_slot(self):
        for path in self._operation_dirs():
            record = self._request_record(path.name)
            if record is None:
                continue
            if not self._event_paths(path.name):
                raise RunError('RUN_BUSY')
            if self.current(path.name).state in NONTERMINAL_STATES:
                raise RunError('RUN_BUSY')

    def _enforce_stage_operation_limit(self):
        count = 0
        for _ in self._iter_operation_dirs():
            count += 1
            if count >= MAX_STAGE_OPERATIONS:
                raise RunError('RUN_LIMIT')

    def _enforce_pending_capacity(self, limit):
        count = 0
        scanned = 0
        for path in self.root.glob('projects/*/stages/*/runtime/operations/*'):
            scanned += 1
            if scanned > MAX_GLOBAL_SCAN:
                raise RunError('RUN_LIMIT')
            try:
                inspect_components(path)
                if not path.is_dir() or re.fullmatch(r'[0-9a-f-]{36}', path.name) is None:
                    continue
                repository = ProjectOperationRepository(
                    self.root,
                    path.parents[2],
                    path.parents[1],
                    self.root_lock,
                    path.parents[1] / 'archive.lock',
                    self.limits,
                )
                if repository._request_record(path.name) is None:
                    continue
                if not repository._event_paths(path.name) or repository.current(path.name).state in NONTERMINAL_STATES:
                    count += 1
                    if count >= limit:
                        raise RunError('RUN_LIMIT')
            except RunError as error:
                if error.code in {'RUN_STORAGE_INVALID', 'RUN_STORAGE_UNAVAILABLE', 'RUN_LIMIT'}:
                    raise
        return count

    def _admit_write(self, operation_id, bytes_count, file_count):
        try:
            admit(self.root, self.stage_root, self._operation_root(operation_id), self.limits,
                  GrowthEstimate(bytes_count, file_count))
        except ArchiveError as error:
            if error.code == 'ARCHIVE_QUOTA_EXCEEDED':
                raise RunError('RUN_LIMIT') from None
            raise self._run_error(error) from None

    def _operation_dirs(self):
        return tuple(self._iter_operation_dirs())

    def _iter_operation_dirs(self):
        if not self.operations.exists():
            return
        try:
            inspect_components(self.operations)
            count = 0
            for path in self.operations.iterdir():
                inspect_components(path)
                if path.is_dir() and re.fullmatch(r'[0-9a-f-]{36}', path.name):
                    count += 1
                    if count > MAX_STAGE_OPERATIONS:
                        raise RunError('RUN_LIMIT')
                    yield path
        except OSError:
            raise RunError('RUN_STORAGE_UNAVAILABLE') from None

    def _operation_root(self, operation_id):
        validate_uuid_text(operation_id)
        try:
            safe_relative_path(f'operations/{operation_id}')
            return controlled_path(self.runtime, f'operations/{operation_id}/request.json').parent
        except ArchiveError as error:
            raise self._run_error(error) from None

    def _run_error(self, error):
        if error.code == 'ARCHIVE_BUSY':
            return RunError('RUN_BUSY')
        if error.code == 'ARCHIVE_QUOTA_EXCEEDED':
            return RunError('RUN_LIMIT')
        if error.code in {'ARCHIVE_ROOT_UNCONFIGURED', 'ARCHIVE_CONFIG_INVALID'}:
            return RunError('RUN_UNAVAILABLE')
        if error.code == 'ARCHIVE_STORAGE_UNAVAILABLE':
            return RunError('RUN_STORAGE_UNAVAILABLE')
        return RunError('RUN_STORAGE_INVALID')
