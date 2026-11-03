from dataclasses import replace
from unittest import TestCase

from project_management.app.domain.capture_values import canonical_bytes, decode_snapshot
from project_management.app.domain.captures import ArchiveError, PartCoverage
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveValueValidation(CaptureArchiveScenario, TestCase):
    def test_collection_coverage_matches_actual_ids_and_counts(self):
        snapshot = self.snapshot(())
        for part in (
            PartCoverage('complete', 'v1', 0, 0, None),
            PartCoverage('complete', 'v1', 1, None, None),
            PartCoverage('access_lost', 'v1', 1, 1, None),
        ):
            malformed = replace(snapshot, coverage=replace(snapshot.coverage, comments=part))
            with self.subTest(part=part), self.assertRaises(ArchiveError):
                decode_snapshot(canonical_bytes(malformed))

    def test_json_never_coerces_key_identity(self):
        with self.assertRaises(ArchiveError):
            canonical_bytes({1: 'original', '1': 'ambiguous'})

    def test_record_id_and_map_key_must_agree(self):
        snapshot = replace(self.snapshot(()), comments_by_id={'one': {'id': 'two', 'body': 'text'}})
        with self.assertRaises(ArchiveError):
            decode_snapshot(canonical_bytes(snapshot))
        numeric = replace(snapshot, comments_by_id={'1': {'id': 1, 'body': 'uncoerced'}})
        with self.assertRaises(ArchiveError):
            decode_snapshot(canonical_bytes(numeric))
