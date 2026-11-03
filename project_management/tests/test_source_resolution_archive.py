from dataclasses import replace
import hashlib
import unittest

from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.capture_archive import (
    ArchiveError, MembershipInput, PartCoverage, SourceDependencyDefinition, SourceResolutionInput,
)
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.app.api.access import ProviderAccessService


class TestSourceResolutionArchive(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldKeepKnownMembershipWhenSealingAFailedCapture(self):
        with self.archive_service() as (_, service):
            intent = self.intent()
            service.prepare(self.actor, intent)
            membership = MembershipInput((self.item(stable_id='101'), self.item(stable_id='102')),
                                         PartCoverage('complete', 'version-1', 2, 2, None), ())
            receipt = service.finalize_partial(self.actor, self.project.id, self.stage.id,
                                               intent.capture_id, failure_code='PROVIDER_NETWORK_ERROR',
                                               membership=membership)
            saved = service.read_capture(self.actor, self.project.id, self.stage.id, intent.capture_id)
            self.assertEqual((True, False, 2), (receipt.membership_complete, receipt.complete, len(saved.membership.items)))

    def definition(self):
        query = 'project = ALPHA'
        return SourceResolutionInput(
            self.stage.definition_hash, 'jira', 'alpha-endpoint', 'principal-1', self.stage.descriptor.query,
            (SourceDependencyDefinition('12', query, hashlib.sha256(query.encode()).hexdigest()),),
            'jira-dc-v1:parser-1',
        )

    def test_shouldBindOneImmutableDefinitionAndReplayOriginalCommit(self):
        with self.archive_service() as (root, service):
            self.assertIsNone(service.read_source_resolution(self.actor, self.project.id, self.stage.id))
            self.assertEqual([], list(root.iterdir()))
            first = service.bind_source_resolution(self.actor, self.project.id, self.stage.id, self.definition())
            scope = ProviderAccessService(service.project_api, None, {}, service).scope(
                self.actor, self.project.id, self.stage.id)
            self.assertEqual((first.resolution_hash, 'principal-1'), (scope.first_resolution_hash, scope.first_principal_id))
            again = service.bind_source_resolution(self.actor, self.project.id, self.stage.id, self.definition())
            self.assertEqual(first, again)
            self.assertEqual(self.definition(), service.read_source_resolution(self.actor, self.project.id, self.stage.id))
            self.assertEqual((), service.list_captures(self.actor, self.project.id, self.stage.id).items)
            with self.assertRaises(ProjectError) as caught:
                service.bind_source_resolution(self.actor, self.project.id, self.stage.id,
                                               replace(self.definition(), principal_id='other-principal'))
            self.assertEqual('SOURCE_CHANGED', caught.exception.code)
            self.assertEqual(first.commit_id, self.git_text(self.archive_path(root), 'rev-parse', 'HEAD'))

    def test_shouldRefuseOwnerAndMalformedSourceBeforeCreatingFiles(self):
        with self.archive_service() as (root, service):
            with self.assertRaises(ProjectError):
                service.bind_source_resolution(ProjectActor('other-owner'), self.project.id,
                                               self.stage.id, self.definition())
            bad = replace(self.definition(), dependencies=(SourceDependencyDefinition('12', 'changed', 'b' * 64),))
            with self.assertRaises(ArchiveError) as caught:
                service.bind_source_resolution(self.actor, self.project.id, self.stage.id, bad)
            self.assertEqual('ARCHIVE_MANIFEST_INVALID', caught.exception.code)
            self.assertEqual([], list(root.iterdir()))

    def test_shouldPreservePartialResponseMetadataAndUnchangedRawBytes(self):
        with self.archive_service() as (root, service):
            intent = self.intent()
            service.prepare(self.actor, intent)
            original = b'{"partial":'
            raw = replace(self.page(original), partial=True, error_code='CAPTURE_RESPONSE_LIMIT')
            ref = service.append_page(self.actor, intent, raw)
            receipt = service.finalize_partial(self.actor, self.project.id, self.stage.id,
                                               intent.capture_id, failure_code='CAPTURE_RESPONSE_LIMIT')
            metadata = self.git(self.archive_path(root), 'show',
                                f'{receipt.commit_id}:captures/{intent.capture_id}/page-intents.json')
            self.assertIn(b'"partial":true', metadata)
            self.assertEqual(original, service.read_page(self.actor, self.project.id, self.stage.id,
                                                        intent.capture_id, ref.page_id))
