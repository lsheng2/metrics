from dataclasses import replace
from datetime import UTC, datetime, timedelta
import unittest

from project_management.app.domain.captures import ArchiveError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class CaptureArchiveRecoveryCase(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldKeepOriginalDeadlineForPreparedCaptureAndAllowPartialSealAfterExpiry(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            expired = self.intent(deadline_at=datetime.now(UTC) - timedelta(seconds=1))
            service.prepare(self.actor, expired)
            renewed = replace(expired, deadline_at=datetime.now(UTC) + timedelta(minutes=10))

            with self.assertRaises(ArchiveError) as raised:
                service.append_page(self.actor, renewed, self.page())

            receipt = service.finalize_partial(
                self.actor,
                self.project.id,
                self.stage.id,
                expired.capture_id,
                failure_code='deadline_expired',
            )
            manifest = service.read_capture(self.actor, self.project.id, self.stage.id, expired.capture_id)
            self.assertEqual(('ARCHIVE_CAPTURE_CONFLICT', False, 'deadline_expired'), (raised.exception.code, receipt.complete, manifest.failure_code))

    def test_shouldReturnOriginalCommitWhenFinalizeIsReplayedAfterReceiptWasPublished(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page_ref = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,)))
            membership = self.membership(page_ref.page_id)

            first = service.finalize(self.actor, intent, membership, complete=True)
            replay = service.finalize(self.actor, intent, membership, complete=True)

            self.assertEqual((first.commit_id, first.manifest_sha256), (replay.commit_id, replay.manifest_sha256))

    def test_shouldSealExistingRawPagesAndSnapshotsWhenFinalizingPartialAfterFailure(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page_ref = service.append_page(self.actor, intent, self.page())
            snapshot_ref = service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,)))

            receipt = service.finalize_partial(
                self.actor,
                self.project.id,
                self.stage.id,
                intent.capture_id,
                failure_code='comments_partial',
            )
            manifest = service.read_capture(self.actor, self.project.id, self.stage.id, intent.capture_id)

            self.assertEqual((False, (snapshot_ref,), (page_ref.page_id,)), (receipt.complete, manifest.snapshots, manifest.membership.raw_page_ids))


if __name__ == '__main__':
    unittest.main()
