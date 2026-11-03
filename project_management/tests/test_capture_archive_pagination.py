import unittest
from dataclasses import replace
from project_management.app.domain.captures import ArchiveError

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class CaptureArchivePaginationCase(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldReturnContinuationWhenCaptureAndSourceChainResultsAreBounded(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            receipts = []
            for suffix in ('A', 'B', 'C'):
                intent = self.intent()
                service.prepare(self.actor, intent)
                page_ref = service.append_page(self.actor, intent, self.page(page_key=f'facts-page-{suffix}'))
                service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,), summary=f'facts {suffix}'))
                receipts.append(service.finalize(self.actor, intent, self.membership(page_ref.page_id), complete=True))

            first_page = service.list_captures(self.actor, self.project.id, self.stage.id, limit=2)
            second_page = service.list_captures(self.actor, self.project.id, self.stage.id, limit=2, after=first_page.next_cursor)
            first_chain = service.source_chain(self.actor, self.project.id, self.stage.id, self.source_key(self.intent()), limit=2)
            second_chain = service.source_chain(
                self.actor,
                self.project.id,
                self.stage.id,
                self.source_key(self.intent()),
                after_capture_id=first_chain.next_cursor,
                limit=2,
            )

            self.assertEqual(
                ([receipts[0].capture_id, receipts[1].capture_id], [receipts[2].capture_id], True, [1, 2], [3]),
                (
                    [receipt.capture_id for receipt in first_page.items],
                    [receipt.capture_id for receipt in second_page.items],
                    first_page.next_cursor is not None,
                    [item.sequence for item in first_chain.items],
                    [item.sequence for item in second_chain.items],
                ),
            )
            with self.assertRaises(ArchiveError):
                service.source_chain(self.actor, self.project.id, self.stage.id,
                                     replace(self.source_key(self.intent()), principal_id='other'),
                                     after_capture_id=first_chain.next_cursor)
            with self.assertRaises(ArchiveError):
                service.list_captures(self.actor, self.project.id, self.stage.id, after='invalid-cursor')
            extra = self.intent()
            service.prepare(self.actor, extra)
            service.finalize_partial(self.actor, self.project.id, self.stage.id, extra.capture_id,
                                     failure_code='later_observation')
            pinned = service.list_captures(self.actor, self.project.id, self.stage.id,
                                          after=first_page.next_cursor, limit=100)
            self.assertEqual([receipts[2].capture_id], [row.capture_id for row in pinned.items])


if __name__ == '__main__':
    unittest.main()
