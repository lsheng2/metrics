from pathlib import Path
import re
import stat

from project_management.app.domain.run_admission_values import validate_stored_request
from project_management.app.domain.run_contracts import OperationLocation, OperationRecoveryCandidate, RunError
from project_management.app.domain.run_values import validate_uuid_text
from project_management.app.domain.captures import ArchiveError
from project_management.storage.locks import exclusive_lock
from project_management.storage.paths import ensure_configured_archive_root, inspect_components
from project_management.storage.project_operations import ProjectOperationRepository


UUID_DIR = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
KNOWN_OPERATION_FILES = {'active.json', 'execution.lock'}


def list_operation_locations(root: Path, *, limit=10000) -> tuple[OperationLocation, ...]:
    if type(limit) is not int or limit < 1:
        raise RunError('RUN_INVALID')
    root = Path(root)
    _configured_root(root)
    try:
        with exclusive_lock(root / 'budget.lock'):
            return _location_snapshot(root, limit)
    except ArchiveError as error:
        raise _run_error(error) from None


def read_operation_recovery_candidate(root: Path, location, archive_limits) -> OperationRecoveryCandidate:
    if not isinstance(location, OperationLocation):
        raise RunError('RUN_INVALID')
    root = Path(root)
    _configured_root(root)
    try:
        validate_uuid_text(location.project_id)
        validate_uuid_text(location.stage_id)
        validate_uuid_text(location.operation_id)
    except RunError:
        raise RunError('RUN_STORAGE_INVALID') from None
    repository = _repository(root, location, archive_limits)
    try:
        record = repository._required_request(location.operation_id)
        _, _, _, _, _ = validate_stored_request(record)
        events = repository._event_paths(location.operation_id)
        if events:
            repository.current(location.operation_id)
        return OperationRecoveryCandidate(
            location,
            record['actor_subject'],
            record['admission_hash'],
            bool(events),
        )
    except RunError as error:
        if error.code == 'RUN_NOT_FOUND':
            raise RunError('RUN_STORAGE_INVALID') from None
        raise


def _repository(root: Path, location: OperationLocation, archive_limits):
    stage_root = root / 'projects' / location.project_id / 'stages' / location.stage_id
    runtime = stage_root / 'runtime'
    return ProjectOperationRepository(
        root,
        stage_root,
        runtime,
        root / 'budget.lock',
        runtime / 'archive.lock',
        archive_limits,
    )


def _configured_root(root: Path) -> None:
    try:
        ensure_configured_archive_root(root)
    except Exception as error:
        code = getattr(error, 'code', '')
        if code in {'ARCHIVE_ROOT_UNCONFIGURED', 'ARCHIVE_CONFIG_INVALID'}:
            raise RunError('RUN_UNAVAILABLE') from None
        if code == 'ARCHIVE_STORAGE_UNAVAILABLE':
            raise RunError('RUN_STORAGE_UNAVAILABLE') from None
        raise RunError('RUN_STORAGE_INVALID') from None


class _ScanBudget:
    def __init__(self, limit):
        self.limit = limit
        self.count = 0

    def consume(self):
        self.count += 1
        if self.count > self.limit:
            raise RunError('RUN_LIMIT')


def _location_snapshot(root: Path, limit: int) -> tuple[OperationLocation, ...]:
    projects = root / 'projects'
    if not projects.exists():
        return ()
    budget = _ScanBudget(limit)
    locations = []
    for project_path in _uuid_children(projects, budget):
        stages = project_path / 'stages'
        if not stages.exists():
            continue
        for stage_path in _uuid_children(stages, budget):
            operations = stage_path / 'runtime' / 'operations'
            if not operations.exists():
                continue
            for operation_path in _operation_children(operations, budget):
                locations.append(OperationLocation(project_path.name, stage_path.name, operation_path.name))
    return tuple(sorted(locations, key=lambda row: (row.project_id, row.stage_id, row.operation_id)))


def _uuid_children(parent: Path, budget: _ScanBudget):
    for path in _children(parent):
        budget.consume()
        if not path.is_dir():
            raise RunError('RUN_STORAGE_INVALID')
        if UUID_DIR.fullmatch(path.name) is None or validate_uuid_text(path.name) != path.name:
            raise RunError('RUN_STORAGE_INVALID')
        yield path


def _operation_children(parent: Path, budget: _ScanBudget):
    for path in _children(parent):
        budget.consume()
        if path.name in KNOWN_OPERATION_FILES and path.is_file():
            continue
        if not path.is_dir():
            raise RunError('RUN_STORAGE_INVALID')
        if UUID_DIR.fullmatch(path.name) is None or validate_uuid_text(path.name) != path.name:
            raise RunError('RUN_STORAGE_INVALID')
        yield path


def _children(parent: Path):
    try:
        inspect_components(parent)
        if not parent.is_dir():
            raise RunError('RUN_STORAGE_INVALID')
        for path in sorted(parent.iterdir(), key=lambda item: item.name):
            inspect_components(path)
            try:
                info = path.lstat()
            except OSError:
                raise RunError('RUN_STORAGE_UNAVAILABLE') from None
            if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                raise RunError('RUN_STORAGE_INVALID')
            yield path
    except OSError:
        raise RunError('RUN_STORAGE_UNAVAILABLE') from None


def _run_error(error):
    if error.code == 'ARCHIVE_BUSY':
        return RunError('RUN_BUSY')
    if error.code == 'ARCHIVE_STORAGE_UNAVAILABLE':
        return RunError('RUN_STORAGE_UNAVAILABLE')
    if error.code in {'ARCHIVE_ROOT_UNCONFIGURED', 'ARCHIVE_CONFIG_INVALID'}:
        return RunError('RUN_UNAVAILABLE')
    return RunError('RUN_STORAGE_INVALID')
