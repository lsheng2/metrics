from unittest import TestCase
from unittest.mock import patch

from project_management.app.domain.captures import ArchiveError
from project_management.storage.repository import CaptureArchiveRepository
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveCommitFailures(CaptureArchiveScenario, TestCase):
    def test_retry_before_ref_publication_reuses_original_candidate(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            candidates = []
            publish = CaptureArchiveRepository._publish

            def fail_once(repository, commit_id, parent):
                candidates.append(commit_id)
                if len(candidates) == 1:
                    raise ArchiveError("ARCHIVE_STORAGE_UNAVAILABLE")
                return publish(repository, commit_id, parent)

            with patch.object(CaptureArchiveRepository, "_publish", fail_once):
                with self.assertRaises(ArchiveError):
                    service.finalize(self.actor, intent, self.membership(page.page_id), complete=True)
                result = service.finalize(self.actor, intent, self.membership(page.page_id), complete=True)
            self.assertEqual([result.commit_id, result.commit_id], candidates)

    def test_snapshot_size_is_admitted_before_writing(self):
        with self.archive_service(limits=self.limits(max_capture_bytes=4 * 1024**2,
                                                    max_raw_page_bytes=8 * 1024**2)) as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            with self.assertRaises(ArchiveError):
                service.append_snapshot(self.actor, intent, self.snapshot((page.page_id,), summary="X" * (5 * 1024**2)))
