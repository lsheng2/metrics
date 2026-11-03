import os
import unittest
from project_management.app.domain.captures import ArchiveError

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class CaptureArchiveGitNativeCase(CaptureArchiveScenario, unittest.TestCase):
    def test_conflicting_expected_head_cannot_publish_a_record(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            repository = service.repository_factory.open(service.config, self.project, self.stage, self.actor.subject)
            head = repository.head()
            with self.assertRaises(ArchiveError) as error:
                repository.append_record('wrong-head', 'captures', {'captures/wrong.json': b'{}'},
                                         expected_head='f' * 40, record_fingerprint='a' * 64)
            self.assertEqual('ARCHIVE_CHAIN_CONFLICT', error.exception.code)
            self.assertEqual(head, repository.head())
    def test_local_git_indirection_is_rejected_before_capture_write(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            git_dir = self.archive_path(root) / '.git'
            (git_dir / 'info').mkdir(exist_ok=True)
            (git_dir / 'info' / 'grafts').write_text('', encoding='ascii')
            with self.assertRaises(ArchiveError):
                service.prepare(self.actor, self.intent())
    def test_shouldIgnoreInheritedGitEnvironmentWhenWritingCaptureCommit(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page_ref = service.append_page(self.actor, intent, self.page())
            service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,)))
            previous = os.environ.get('GIT_DIR')
            os.environ['GIT_DIR'] = str(root / 'not-the-archive.git')
            try:
                receipt = service.finalize(self.actor, intent, self.membership(page_ref.page_id), complete=True)
            finally:
                if previous is None:
                    os.environ.pop('GIT_DIR', None)
                else:
                    os.environ['GIT_DIR'] = previous

            self.assertEqual(receipt.commit_id, self.git_text(self.archive_path(root), 'rev-parse', 'main'))

    def test_shouldCommitHistoryButNotOverwriteHumanEditedMaterializedCheckout(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            first_intent = self.intent()
            service.prepare(self.actor, first_intent)
            first_page = service.append_page(self.actor, first_intent, self.page())
            service.append_snapshot(self.actor, first_intent, self.snapshot((first_page.page_id,)))
            first = service.finalize(self.actor, first_intent, self.membership(first_page.page_id), complete=True)
            edited_manifest = self.archive_path(root) / 'captures' / first_intent.capture_id / 'manifest.json'
            edited_manifest.write_text('human edit', encoding='utf-8')
            second_intent = self.intent()
            service.prepare(self.actor, second_intent)
            second_page = service.append_page(self.actor, second_intent, self.page(page_key='facts-page-2'))
            service.append_snapshot(self.actor, second_intent, self.snapshot((second_page.page_id,), summary='new facts'))

            second = service.finalize(self.actor, second_intent, self.membership(second_page.page_id), complete=True)

            self.assertEqual(('stale', 'human edit'), (second.checkout_state, edited_manifest.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
