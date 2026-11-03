from pathlib import Path
from django.conf import settings

from project_management.app.api import ApiForProjectManagement
from project_management.app.api.capture_archive import ArchiveError, ArchiveLimits, ArchiveStorageConfig, CaptureArchiveService
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.out.dashboard_scope_catalog import DashboardScopeCatalog


def build_project_api() -> ApiForProjectManagement:
    return ApiForProjectManagement(DashboardScopeCatalog())


def archive_config_from_settings(source):
    root = getattr(source, 'METRICS_PROJECT_ARCHIVE_ROOT', '')
    if not isinstance(root, str) or not root:
        raise ArchiveError('ARCHIVE_ROOT_UNCONFIGURED')
    defaults = {
        'max_root_bytes': 50 * 1024**3, 'max_root_files': 1000000,
        'max_stage_bytes': 10 * 1024**3, 'max_stage_files': 200000,
        'max_capture_bytes': 256 * 1024**2, 'max_capture_files': 100000,
        'max_raw_page_bytes': 16 * 1024**2, 'max_object_bytes': 32 * 1024**2,
    }
    values = {key: getattr(source, 'METRICS_PROJECT_ARCHIVE_' + key.upper(), value)
              for key, value in defaults.items()}
    return ArchiveStorageConfig(
        Path(root), getattr(source, 'METRICS_PROJECT_ARCHIVE_AUTHOR_NAME', ''),
        getattr(source, 'METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL', ''), ArchiveLimits(**values),
    )


def build_capture_archive_service(config=None, project_api=None):
    return CaptureArchiveService(project_api or build_project_api(), LocalArchiveRepositoryFactory(),
                                 config or archive_config_from_settings(settings))
