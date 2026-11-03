from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveReviewRegressions(CaptureArchiveScenario, TestCase):
    def test_display_key_rename_preserves_page_identity_and_item_ownership(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            original_page = self.page()
            original = service.append_page(self.actor, intent, original_page)
            renamed = replace(self.item(), display_key='RENAMED-1')
            repeated = service.append_page(self.actor, intent, replace(original_page, item=renamed))
            self.assertEqual(original.page_id, repeated.page_id)
            with self.assertRaises(ArchiveError):
                service.append_page(self.actor, intent, replace(original_page, item=renamed, payload=b'different'))
            reference = service.append_snapshot(self.actor, intent, self.snapshot((original.page_id,), item=renamed))
            self.assertEqual(renamed, reference.identity)

    def test_new_object_limit_does_not_block_existing_committed_raw_page(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            service.finalize_partial(self.actor, self.project.id, self.stage.id, intent.capture_id,
                                     failure_code='partial')
            reader = type(service)(service.project_api, service.repository_factory,
                                   replace(service.config, limits=replace(service.config.limits, max_object_bytes=1)))
            self.assertEqual(self.page().payload, reader.read_page(self.actor, self.project.id,
                                                                 self.stage.id, intent.capture_id, page.page_id))

    def test_source_changed_after_collection_cannot_finalize_complete(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            service.project_api.stage = replace(self.stage, source_status='source_changed')
            with self.assertRaises(ProjectError):
                service.finalize(self.actor, intent, self.membership(page.page_id), complete=True)
            result = service.finalize_partial(self.actor, self.project.id, self.stage.id, intent.capture_id,
                                              failure_code='source_changed')
            self.assertFalse(result.complete)

    def test_snapshot_cannot_claim_raw_page_of_other_item(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page(item=self.item(stable_id='OTHER')))
            with self.assertRaises(ArchiveError):
                service.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))

    def test_identical_snapshot_replay_does_not_require_new_allocation(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            snapshot = self.snapshot((page.page_id,))
            original = service.append_snapshot(self.actor, intent, snapshot)
            with patch('project_management.services.capture_archive.admit',
                       side_effect=ArchiveError('ARCHIVE_QUOTA_EXCEEDED')):
                replay = service.append_snapshot(self.actor, intent, snapshot)
            self.assertEqual(original, replay)
