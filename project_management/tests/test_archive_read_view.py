from dataclasses import replace
import unittest

from project_management.app.domain.captures import ArchiveError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveReadView(CaptureArchiveScenario, unittest.TestCase):
    def test_absent_archive_still_rechecks_stage_definition(self):
        with self.archive_service() as (root, service):
            with self.assertRaises(ArchiveError) as error:
                with service._report_read_view(self.actor, self.project.id, self.stage.id, allow_absent=True) as view:
                    self.assertIsNone(view)
                    service.project_api.stage = replace(self.stage, definition_hash='f' * 64)
            self.assertEqual('ARCHIVE_IDENTITY_MISMATCH', error.exception.code)

    def test_reads_binary_history_at_fixed_head_and_observes_next_scope(self):
        from project_management.storage.archive_read_view import GitArchiveReadView
        from project_management.app.spi.archive_reads import ArchiveBlobRequest

        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            repository = service.repository_factory.open(service.config, self.project, self.stage, self.actor.subject)
            first = repository.append_record(
                'first', 'captures', {'captures/first.json': b'alpha\n\x00omega'},
                expected_head=repository.head(), record_fingerprint='a' * 64,
            )
            with GitArchiveReadView(repository) as view:
                self.assertEqual(first.commit_id, view.head())
                requests = (ArchiveBlobRequest(first.commit_id, 'captures/first.json', 100),) * 2
                self.assertEqual((b'alpha\n\x00omega',) * 2, view.read_files(requests))
                second = repository.append_record(
                    'second', 'captures', {'captures/second.json': b'new'},
                    expected_head=repository.head(), record_fingerprint='b' * 64,
                )
                self.assertEqual(('captures/first.json',), view.list_files('captures'))
                self.assertIsNone(view.find_commit_for_path('captures/second.json'))
                self.assertEqual(first.commit_id, view.commit_for_path('captures/first.json'))
                with self.assertRaises(ArchiveError):
                    view.read_file('captures/second.json', second.commit_id)
            with self.assertRaises(ArchiveError):
                view.read_file('captures/first.json')
            with GitArchiveReadView(repository) as fresh:
                self.assertEqual(b'new', fresh.read_file('captures/second.json'))

    def test_batch_provenance_and_checkout_match_original_reader(self):
        from project_management.storage.archive_read_view import GitArchiveReadView
        from project_management.storage.archive_read_history import read_tree

        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            repository = service.repository_factory.open(service.config, self.project, self.stage, self.actor.subject)
            first = repository.append_record('first', 'captures', {'captures/a.json': b'A'},
                                             expected_head=repository.head(), record_fingerprint='a' * 64)
            second = repository.append_record('second', 'captures', {'captures/b.json': b'B'},
                                              expected_head=repository.head(), record_fingerprint='b' * 64)
            expected = {commit: repository.checkout_state(commit) for commit in (first.commit_id, second.commit_id)}
            with GitArchiveReadView(repository) as view:
                self.assertEqual(expected, view.checkout_states(tuple(expected)))
                self.assertEqual(read_tree(repository.git.run, second.commit_id), view._tree(second.commit_id))
                for path in ('captures/a.json', 'captures/b.json'):
                    self.assertEqual(repository.commit_for_path(path), view.commit_for_path(path))
            (repository.archive / 'captures' / 'b.json').write_bytes(b'human')
            with GitArchiveReadView(repository) as view:
                self.assertEqual('stale', view.checkout_state(second.commit_id))
                self.assertEqual(b'B', view.read_file('captures/b.json'))

    def test_budget_rejects_before_body_read_and_never_extends_deadline(self):
        from project_management.storage.archive_read_view import GitArchiveReadView
        from project_management.app.spi.archive_reads import ArchiveBlobRequest

        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            repository = service.repository_factory.open(service.config, self.project, self.stage, self.actor.subject)
            with GitArchiveReadView(repository, max_bytes=1) as view:
                with self.assertRaises(ArchiveError) as error:
                    view.read_files((ArchiveBlobRequest(view.head(), f'bootstrap/stages/{self.stage.id}.json', 10000),))
                self.assertEqual('ARCHIVE_QUOTA_EXCEEDED', error.exception.code)
