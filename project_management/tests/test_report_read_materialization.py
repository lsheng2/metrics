import unittest

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from scripts.validation.report_read_git import fast_import_records


class TestReadFixtureMaterialization(CaptureArchiveScenario, unittest.TestCase):
    def test_native_fixture_import_materializes_exact_files_and_index(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            repository = service.repository_factory.open(service.config, self.project, self.stage, self.actor.subject)
            fast_import_records(repository, [('first', {'captures/first.json': b'{}'}, 'a' * 64, '')])
            self.assertEqual(b'{}', repository.read_file('captures/first.json'))
            self.assertEqual('current', repository.checkout_state(repository.head()))
