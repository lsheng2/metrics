from dataclasses import fields, replace
from unittest import TestCase
from unittest.mock import Mock

from project_management.app.domain.captures import ArchiveError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveInputAtomicity(CaptureArchiveScenario, TestCase):
    def test_read_paths_reject_noncanonical_project_and_stage_before_project_lookup(self):
        with self.archive_service() as (_, service):
            lookup = Mock(side_effect=AssertionError('Noncanonical identity reached Project API'))
            service.project_api.get_project = lookup
            actions = (
                lambda p, s: service.initialize_stage(self.actor, p, s),
                lambda p, s: service.read_capture(self.actor, p, s, self.intent().capture_id),
                lambda p, s: service.read_page(self.actor, p, s, self.intent().capture_id, 'a' * 64),
                lambda p, s: service.list_captures(self.actor, p, s),
                lambda p, s: service.source_chain(self.actor, p, s, self.source_key(self.intent())),
                lambda p, s: service.finalize_partial(self.actor, p, s, self.intent().capture_id, failure_code='test'),
            )
            for index, action in enumerate(actions):
                for project, stage in ((self.project.id.upper(), self.stage.id),
                                       (self.project.id, self.stage.id.upper())):
                    with self.subTest(action=index, project=project), self.assertRaises(ArchiveError):
                        action(project, stage)
            self.assertEqual(0, lookup.call_count)
    def test_uuid_fields_use_one_canonical_form_before_immutable_paths(self):
        with self.archive_service() as (root, service):
            intent = self.intent()
            for name in ('project_id', 'stage_id', 'capture_id', 'request_id'):
                value = getattr(intent, name).upper()
                with self.subTest(field=name), self.assertRaises(ArchiveError):
                    service.prepare(self.actor, replace(intent, **{name: value}))
                self.assertEqual([], list(root.iterdir()))
    def test_all_source_and_intent_scalars_are_validated_before_first_write(self):
        with self.archive_service() as (root, service):
            original = self.intent()
            for name in ('endpoint_id', 'principal_id', 'credential_revision'):
                for value in (123, True, ['text'], '', None):
                    with self.subTest(name=name, value=value), self.assertRaises(ArchiveError):
                        service.prepare(self.actor, replace(original, source=replace(original.source, **{name: value})))
                    self.assertEqual([], list(root.iterdir()))
            for value in (123, True, ['text'], 'not-a-hash'):
                with self.subTest(value=value), self.assertRaises(ArchiveError):
                    service.prepare(self.actor, replace(original, original_input_hash=value))
                self.assertEqual([], list(root.iterdir()))

    def test_raw_page_metadata_is_refused_before_object_or_intent_is_written(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
            for name in ('page_key', 'content_type', 'request_fingerprint'):
                for value in (1, True, [], '', None):
                    with self.subTest(name=name, value=value), self.assertRaises(ArchiveError):
                        service.append_page(self.actor, intent, replace(self.page(), **{name: value}))
                    after = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
                    self.assertEqual(before, after)
