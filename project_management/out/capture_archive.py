from project_management.storage.repository import CaptureArchiveRepository


class LocalArchiveRepositoryFactory:
    def open(self, config, project, stage, owner_subject):
        return CaptureArchiveRepository(config, project, stage, owner_subject)
