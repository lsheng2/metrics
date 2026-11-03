from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from project_management.app.api.capture_archive import ArchiveError
from project_management.container import archive_config_from_settings


class TestArchiveConfiguration(TestCase):
    def test_unconfigured_root_does_not_inherit_state_or_code_directory(self):
        with self.assertRaises(ArchiveError) as error:
            archive_config_from_settings(SimpleNamespace(METRICS_PROJECT_ARCHIVE_ROOT='', METRICS_STATE_DIR='D:/other'))
        self.assertEqual('ARCHIVE_ROOT_UNCONFIGURED', error.exception.code)

    def test_explicit_root_and_author_are_preserved_without_initializing_storage(self):
        config = archive_config_from_settings(SimpleNamespace(
            METRICS_PROJECT_ARCHIVE_ROOT='D:/synthetic-archive-not-created',
            METRICS_PROJECT_ARCHIVE_AUTHOR_NAME='Operator',
            METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL='operator@example.test',
        ))
        self.assertEqual(Path('D:/synthetic-archive-not-created'), config.root)
        self.assertEqual(50 * 1024**3, config.limits.max_root_bytes)
