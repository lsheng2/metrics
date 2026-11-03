from contextlib import contextmanager

from project_management.app.domain.captures import ArchiveError
from project_management.storage.paths import inspect_components, read_bytes, validate_uuid
from project_management.storage.staging import active_capture_path


class ReportArchiveRepositoryAccess:
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
    def _report_repository(self, actor, project_id, stage_id, *, write=False):
        project, stage = self._stage_for_write(actor, project_id, stage_id) if write else self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
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
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.verify_identity()
            yield repository
