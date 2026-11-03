from dataclasses import replace
from datetime import UTC, datetime, timedelta
import os
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch

from project_management.app.domain.captures import ArchiveError, MembershipInput, PartCoverage, WorkItemIdentity
from project_management.storage.staging import PendingCaptureStore
from project_management.storage.locks import exclusive_lock
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveFailureRecovery(CaptureArchiveScenario, TestCase):
    def test_raw_object_without_receipt_is_recovered_and_sealed_as_partial(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            with patch.object(PendingCaptureStore, 'write_page_receipt', side_effect=ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')):
                with self.assertRaises(ArchiveError):
                    service.append_page(self.actor, intent, self.page(payload=b'preserved intermediate response'))
            result = service.finalize_partial(self.actor, self.project.id, self.stage.id, intent.capture_id,
                                              failure_code='interrupted')
            manifest = service.read_capture(self.actor, self.project.id, self.stage.id, intent.capture_id)
            self.assertFalse(result.complete)
            self.assertEqual(1, len(manifest.pages))
            self.assertEqual(b'preserved intermediate response', service.read_page(
                self.actor, self.project.id, self.stage.id, intent.capture_id, manifest.pages[0].page_id,
            ))

    def test_complete_membership_with_pending_detail_is_an_honest_partial_capture(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            membership = MembershipInput(
                (self.item(), WorkItemIdentity(self.item().provider_id, self.item().endpoint_id, 'second-id', 'OTHER-2')),
                PartCoverage('complete', 'v1', 2, 2, None), (page.page_id,),
            )
            result = service.finalize(self.actor, intent, membership, complete=False, failure_code='details_pending')
            self.assertTrue(result.membership_complete)
            self.assertFalse(result.complete)
            self.assertEqual(1, len(result.snapshots))
            with self.assertRaises(ArchiveError):
                service.append_page(self.actor, intent, self.page(page_key='late'))

    def test_root_budget_lock_blocks_another_process_without_leaking_lock(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            code = (
                "import sys\nfrom pathlib import Path\n"
                "from project_management.storage.locks import exclusive_lock\n"
                "from project_management.app.domain.captures import ArchiveError\n"
                "try:\n"
                " with exclusive_lock(Path(sys.argv[1])): print('ACQUIRED')\n"
                "except ArchiveError as error: print(error.code)\n"
            )
            with exclusive_lock(root / 'budget.lock'):
                result = subprocess.run([sys.executable, '-c', code, str(root / 'budget.lock')],
                                        capture_output=True, text=True, timeout=10,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual('ARCHIVE_BUSY', result.stdout.strip())
            prepared = service.prepare(self.actor, self.intent())
            self.assertEqual('prepared', prepared.state)

    def test_reduced_new_limits_do_not_prevent_sealing_existing_raw_evidence(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = service.append_page(self.actor, intent, self.page())
            reduced = type(service)(
                service.project_api, service.repository_factory,
                replace(service.config, limits=replace(service.config.limits, max_capture_bytes=1)),
            )
            receipt = reduced.finalize_partial(self.actor, self.project.id, self.stage.id, intent.capture_id,
                                               failure_code='limits_changed')
            self.assertFalse(receipt.complete)
            self.assertEqual(self.page().payload, reduced.read_page(
                self.actor, self.project.id, self.stage.id, intent.capture_id, page.page_id,
            ))
