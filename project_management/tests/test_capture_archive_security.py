from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import portalocker

from project_management.app.domain.captures import ArchiveError, ArchiveStorageConfig
from project_management.app.api.capture_archive import CaptureArchiveService
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario, ProjectApiStub


class CaptureArchiveSecurityCase(CaptureArchiveScenario, unittest.TestCase):
    def test_wrong_rule_and_principal_source_reads_do_not_cross_history(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            wrong = replace(intent, source=replace(intent.source, rule_hash='b' * 64))
            with self.assertRaises(ArchiveError):
                service.prepare(self.actor, wrong)
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            service.finalize(self.actor, intent, self.membership(page.page_id), complete=True)
            with self.assertRaises(ArchiveError):
                service.read_page(self.actor, self.project.id, self.stage.id, intent.capture_id, 'f' * 64)
            self.assertEqual((), service.source_chain(
                self.actor, self.project.id, self.stage.id,
                replace(self.source_key(intent), principal_id='other-principal'),
            ).items)
            object_path = root / 'projects' / self.project.id / 'stages' / self.stage.id / 'objects' / 'sha256' / page.sha256 / 'payload'
            object_path.write_bytes(b'corrupt')
            with self.assertRaises(ArchiveError) as caught:
                service.read_page(self.actor, self.project.id, self.stage.id, intent.capture_id, page.page_id)
            self.assertEqual('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED', caught.exception.code)

    def test_shouldRejectSnapshotIdentityFromDifferentEndpointBeforeStaging(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page_ref = service.append_page(self.actor, intent, self.page())
            wrong_endpoint = replace(self.item(), endpoint_id='other-endpoint')

            with self.assertRaises(ArchiveError) as raised:
                service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,), item=wrong_endpoint))

            self.assertEqual('ARCHIVE_IDENTITY_MISMATCH', raised.exception.code)

    def test_shouldValidateArchiveIdentityBeforeReadAccess(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page_ref = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,)))
            service.finalize(self.actor, intent, self.membership(page_ref.page_id), complete=True)
            (root / 'archive-root.json').write_text('{"schema_version":1,"root_id":"changed"}', encoding='utf-8')

            with self.assertRaises(ArchiveError) as raised:
                service.read_capture(self.actor, self.project.id, self.stage.id, intent.capture_id)

            self.assertEqual('ARCHIVE_IDENTITY_MISMATCH', raised.exception.code)

    def test_shouldRejectArchiveRootInsideCodeCheckoutBeforeCreatingLockFiles(self):
        with TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary) / 'archive-root'
            root.mkdir()
            service = CaptureArchiveService(
                ProjectApiStub(self.project, self.stage),
                LocalArchiveRepositoryFactory(),
                ArchiveStorageConfig(root, 'Archive Test', 'archive@example.test', self.limits()),
            )

            with self.assertRaises(ArchiveError) as raised:
                service.initialize_stage(self.actor, self.project.id, self.stage.id)

            self.assertEqual(('ARCHIVE_CONFIG_INVALID', False), (raised.exception.code, (root / 'budget.lock').exists()))

    def test_shouldReleaseRootBudgetLockWhenStageLockIsBusy(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            stage_lock = root / 'projects' / self.project.id / 'stages' / self.stage.id / 'runtime' / 'archive.lock'
            with portalocker.Lock(stage_lock, timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
                with self.assertRaises(ArchiveError) as raised:
                    service.prepare(self.actor, self.intent())
                with portalocker.Lock(root / 'budget.lock', timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
                    root_lock_released = True

            self.assertEqual(('ARCHIVE_BUSY', True), (raised.exception.code, root_lock_released))


if __name__ == '__main__':
    unittest.main()
