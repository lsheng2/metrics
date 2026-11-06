from contextlib import contextmanager

from project_management.app.domain.captures import ArchiveError
from project_management.storage.paths import inspect_components, read_bytes, validate_uuid
from project_management.storage.locks import exclusive_lock
from project_management.storage.staging import active_capture_path


class ReportArchiveRepositoryAccess:
    @contextmanager
    def _report_read_view(self, actor, project_id, stage_id, *, allow_absent=False):
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
        repository = self.repository_factory.open(self.config, project, stage, actor.subject)
        if allow_absent:
            inspect_components(repository.stage_root)
            if not repository.stage_root.exists():
                yield None
                self._recheck_read_stage(actor, project_id, stage_id, stage.definition_hash)
                return
        repository.verify_identity()
        with repository.open_read_view() as view:
            yield view
            self._recheck_read_stage(actor, project_id, stage_id, stage.definition_hash)

    def _recheck_read_stage(self, actor, project_id, stage_id, expected_hash):
        _, current = self._stage_for_read(actor, project_id, stage_id)
        if current.definition_hash != expected_hash:
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')

    @contextmanager
    def _meeting_calendar_repository(self, actor, project_id, stage_id):
        self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
        # All stage writers take this root lock first; an absent stage stays absent.
        with exclusive_lock(self.config.root / 'budget.lock'):
            project, stage = self._stage_for_write(actor, project_id, stage_id)
            if self.stage_archive_status(actor, project_id, stage_id) == 'absent':
                yield None
            else:
                repository = self.repository_factory.open(self.config, project, stage, actor.subject)
                repository.verify_identity()
                yield repository

    def stage_archive_status(self, actor, project_id, stage_id):
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
        stage_root = self.config.root / 'projects' / validate_uuid(project.id) / 'stages' / validate_uuid(stage.id)
        inspect_components(stage_root)
        if not stage_root.exists():
            return 'absent'
        if not stage_root.is_dir():
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        repository = self.repository_factory.open(self.config, project, stage, actor.subject)
        repository.verify_identity()
        return 'ready'

    @contextmanager
    def _report_repository(self, actor, project_id, stage_id, *, write=False, _read_view=None):
        project, stage = self._stage_for_write(actor, project_id, stage_id) if write else self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
        if _read_view is not None:
            if write:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            if (_read_view.root != self.config.root.absolute() or _read_view.project.id != project.id
                    or _read_view.stage.id != stage.id or _read_view.owner_subject != actor.subject
                    or _read_view.stage.definition_hash != stage.definition_hash):
                raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
            with _read_view.open_read_view() as view:
                yield view
            self._recheck_read_stage(actor, project_id, stage_id, stage.definition_hash)
            return
        if write:
            with self._locks(project, stage):
                project, stage = self._stage_for_write(actor, project_id, stage_id)
                repository = self.repository_factory.open(self.config, project, stage, actor.subject)
                repository.verify_identity()
                if (repository.runtime / active_capture_path(repository.runtime)).exists():
                    read_bytes(repository.runtime, active_capture_path(repository.runtime))
                    raise ArchiveError('ARCHIVE_BUSY')
                yield repository
        else:
            with self._report_read_view(actor, project_id, stage_id) as view:
                yield view
