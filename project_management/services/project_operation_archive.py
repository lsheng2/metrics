from project_management.app.domain.captures import ArchiveError
from project_management.storage.project_operations import ProjectOperationRepository


class ProjectOperationArchive:
    def project_operation_repository(self, actor, project_id, stage_id, *, write=False, initialize=False):
        access = self._stage_for_write if initialize else self._stage_for_read
        project, stage = access(actor, project_id, stage_id)
        self._validate_root_before_lock()
        if initialize:
            with self._locks(project, stage):
                project, stage = self._stage_for_write(actor, project_id, stage_id)
                repository = self.repository_factory.open(self.config, project, stage, actor.subject)
                repository.initialize()
        else:
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            if not repository.stage_root.exists():
                raise ArchiveError('ARCHIVE_RAW_PAGE_MISSING')
            repository.verify_identity()
        return ProjectOperationRepository(
            self.config.root,
            repository.stage_root,
            repository.runtime,
            self.config.root / 'budget.lock',
            repository.runtime / 'archive.lock',
            self.config.limits,
        )
