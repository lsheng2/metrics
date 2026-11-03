import unittest

from project_management.app.domain.captures import ArchiveError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class CaptureArchiveBudgetCase(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldRejectOversizedRawPageWithoutAdvancingCompleteCapture(self):
        limits = self.limits(max_raw_page_bytes=8, max_object_bytes=32)
        with self.archive_service(limits=limits) as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)

            with self.assertRaises(ArchiveError) as raised:
                service.append_page(self.actor, intent, self.page(payload=b'this payload is too large'))

            receipt = service.finalize_partial(
                self.actor,
                self.project.id,
                self.stage.id,
                intent.capture_id,
                failure_code='raw_page_too_large',
            )
            manifest = service.read_capture(self.actor, self.project.id, self.stage.id, intent.capture_id)
            self.assertEqual(('ARCHIVE_QUOTA_EXCEEDED', False, 0), (raised.exception.code, receipt.complete, len(manifest.pages)))

    def test_shouldRetainUnresolvedReservationAfterQuotaFailureSoLaterRetryCannotPretendSpaceWasFree(self):
        limits = self.limits(max_capture_bytes=3 * 1024 * 1024)
        with self.archive_service(limits=limits) as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)

            with self.assertRaises(ArchiveError):
                service.append_page(self.actor, intent, self.page(payload=b'x' * (1024 * 1024)))
            receipt = service.finalize_partial(
                self.actor,
                self.project.id,
                self.stage.id,
                intent.capture_id,
                failure_code='quota_failed',
            )

            self.assertEqual((False, 'quota_failed'), (receipt.complete, receipt.failure_code))

    def test_shouldApplyCaptureFileQuotaBeforePreparingIntent(self):
        limits = self.limits(max_capture_files=1)
        with self.archive_service(limits=limits) as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)

            with self.assertRaises(ArchiveError) as raised:
                service.prepare(self.actor, self.intent())

            self.assertEqual('ARCHIVE_QUOTA_EXCEEDED', raised.exception.code)


if __name__ == '__main__':
    unittest.main()
