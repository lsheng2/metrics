from dataclasses import replace
import unittest

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.captures import MembershipInput, PartCoverage
from project_management.tests.report_source_fixtures import ReportSourceScenario


class TestReportMembershipProjection(ReportSourceScenario, unittest.TestCase):
    def test_shouldExposeCompletePinnedMembershipProofWithRawPageEvidence(self):
        with self.archive_service() as (_, archive):
            captured = self.capture_summary_source(archive)
            snapshot = self.read_report_source(archive, captured.capture_id)

            membership = archive.read_report_membership(
                self.actor,
                self.project.id,
                self.stage.id,
                snapshot,
            )

            assert membership.state == 'complete'
            assert membership.principal_id == snapshot.rows[0].source_key.principal_id
            assert membership.members[0].identity == snapshot.rows[0].identity
            assert membership.proof_hash

    def test_shouldReturnUnknownWhenMembershipRawPageEvidenceIsMissing(self):
        with self.archive_service() as (_, archive):
            intent = self.intent()
            prepared = archive.prepare(self.actor, intent)
            page = archive.append_page(self.actor, intent, self.page())
            snapshot = archive.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            receipt = archive.finalize(
                self.actor,
                intent,
                MembershipInput(
                    (self.item(),),
                    PartCoverage('complete', 'source-version-1', 1, 1, None),
                    (),
                ),
                complete=True,
            )
            source_reader = report_api.ReportSourceReader(archive, self.contract)
            report_snapshot = source_reader.read(
                self.actor,
                self.project.id,
                self.stage.id,
                report_api.ReportSelection(capture_id=intent.capture_id),
            )

            membership = archive.read_report_membership(
                self.actor,
                self.project.id,
                self.stage.id,
                report_snapshot,
            )

            assert membership.state == 'unknown'

    def test_shouldAcceptPlainJsonMembershipPageEvidence(self):
        with self.archive_service() as (_, archive):
            intent = self.intent()
            archive.prepare(self.actor, intent)
            page = archive.append_page(self.actor, intent, replace(self.page(), content_type='application/json'))
            archive.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            archive.finalize(
                self.actor,
                intent,
                MembershipInput((self.item(),), PartCoverage('complete', 'source-version-1', 1, 1, None), (page.page_id,)),
                complete=True,
            )
            source_reader = report_api.ReportSourceReader(archive, self.contract)
            report_snapshot = source_reader.read(
                self.actor,
                self.project.id,
                self.stage.id,
                report_api.ReportSelection(capture_id=intent.capture_id),
            )
            membership = archive.read_report_membership(self.actor, self.project.id, self.stage.id, report_snapshot)

            assert membership.state == 'complete'

    def test_shouldReturnUnknownWhenMembershipPageIntentWasPartial(self):
        with self.archive_service() as (_, archive):
            intent = self.intent()
            archive.prepare(self.actor, intent)
            page = archive.append_page(self.actor, intent, replace(
                self.page(),
                partial=True,
                error_code='CAPTURE_RESPONSE_LIMIT',
            ))
            archive.append_snapshot(self.actor, intent, self.snapshot((page.page_id,)))
            archive.finalize(
                self.actor,
                intent,
                MembershipInput((self.item(),), PartCoverage('complete', 'source-version-1', 1, 1, None), (page.page_id,)),
                complete=True,
            )
            source_reader = report_api.ReportSourceReader(archive, self.contract)
            report_snapshot = source_reader.read(
                self.actor,
                self.project.id,
                self.stage.id,
                report_api.ReportSelection(capture_id=intent.capture_id),
            )

            membership = archive.read_report_membership(self.actor, self.project.id, self.stage.id, report_snapshot)

            assert membership.state == 'unknown'

    def test_shouldReturnUnknownWhenPinnedAdmissionIntentHashOrLimitIsInvalid(self):
        from project_management.app.domain.capture_values import canonical_bytes, decode_json

        for mutation in ('wrong_intent', 'missing_limit'):
            with self.subTest(mutation=mutation), self.archive_service() as (root, archive):
                captured = self.capture_summary_source(archive)
                archive_root = self.archive_path(root)
                path = archive_root / f'captures/{captured.capture_id}/admission.json'
                value = decode_json(path.read_bytes())
                if mutation == 'wrong_intent':
                    value['intent_hash'] = '0' * 64
                else:
                    value['limits'].pop('max_object_bytes')
                path.write_bytes(canonical_bytes(value))
                self.git(archive_root, 'add', '--', f'captures/{captured.capture_id}/admission.json')
                self.git(archive_root, 'commit', '-m', f'corrupt admission {mutation}')
                report_snapshot = self.read_report_source(archive, captured.capture_id)

                membership = archive.read_report_membership(self.actor, self.project.id, self.stage.id, report_snapshot)

                assert membership.state == 'unknown'
