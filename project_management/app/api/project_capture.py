from project_management.app.api.capture_archive import ArchiveError
from project_management.services.capture import ProjectCaptureService
from provider_sync.app.api.access_factory import create_provider_access_service


def build_project_capture_service():
    access = create_provider_access_service()
    if access.archive is None:
        raise ArchiveError('ARCHIVE_ROOT_UNCONFIGURED')
    return ProjectCaptureService(access.project_api, access, access.archive)


__all__ = ['ProjectCaptureService', 'build_project_capture_service']
