import unittest

from project_management.app.api import ProjectError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from project_management.services.capture import ProjectCaptureService
from provider_sync.app.api.access_contracts import CaptureLimits
from provider_sync.tests.capture_gateway_fixtures import JiraFixture, issue


class TestProjectCapturePipeline(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldCommitCompleteSourceAndReadItThroughPublicProviderApi(self):
        with self.archive_service() as (_, archive):
            provider = JiraFixture(self, archive=archive)
            capture = ProjectCaptureService(provider.project_api, provider.service, archive)
            context = provider.context()
            receipt = capture.capture(context)
            self.assertTrue(receipt.complete)
            snapshot = provider.service.read_item(self.actor, self.project.id, self.stage.id,
                                                  context.capture_id, '101')
            self.assertEqual(['A', 'B', 'C'], [row['body'] for row in snapshot.comments_by_id.values()])
            resolution = archive.read_source_resolution(self.actor, self.project.id, self.stage.id)
            self.assertEqual('principal-1', resolution.principal_id)

    def test_shouldRetainAllFiveHundredMembersWithOnlyOneDetailAndPendingRemainder(self):
        with self.archive_service() as (_, archive):
            provider = JiraFixture(self, archive=archive)
            provider.rows = [issue(str(index)) for index in range(101, 601)]
            context = provider.context(limits=CaptureLimits(max_details=1, page_size=100))
            receipt = ProjectCaptureService(provider.project_api, provider.service, archive).capture(context)
            manifest = archive.read_capture(self.actor, self.project.id, self.stage.id, context.capture_id)
            self.assertEqual((True, False, 500, 1, 'CAPTURE_DETAILS_PENDING'),
                             (receipt.membership_complete, receipt.complete, len(manifest.membership.items),
                              len(receipt.snapshots), receipt.failure_code))
            self.assertEqual(2, sum('/issue/' in path and not path.endswith('/comment')
                                    for _, path, _ in provider.transport.requests))

    def test_shouldKeepEarlierCommentsWhenLaterPageLosesAccess(self):
        with self.archive_service() as (_, archive):
            provider = JiraFixture(self, archive=archive)
            original = provider.respond

            def respond(path, params):
                if path.endswith('/comment') and params['startAt'] == '2':
                    return 403, {'errorMessages': ['No access.']}
                return original(path, params)

            provider.transport.responder = respond
            context = provider.context()
            receipt = ProjectCaptureService(provider.project_api, provider.service, archive).capture(context)
            snapshot = provider.service.read_item(self.actor, self.project.id, self.stage.id,
                                                  context.capture_id, '101')
            self.assertEqual((False, 'partial', ['201', '202']),
                             (receipt.complete, snapshot.coverage.comments.state, list(snapshot.comments_by_id)))

    def test_shouldRejectChangedVerifiedPrincipalBeforeCreatingAnotherCapture(self):
        with self.archive_service() as (_, archive):
            provider = JiraFixture(self, archive=archive)
            service = ProjectCaptureService(provider.project_api, provider.service, archive)
            service.capture(provider.context())
            provider.principal = 'different-principal'
            with self.assertRaises(ProjectError) as caught:
                service.capture(provider.context())
            self.assertEqual('SOURCE_CHANGED', caught.exception.code)
            self.assertEqual(1, len(archive.list_captures(self.actor, self.project.id, self.stage.id).items))

    def test_shouldSealOriginalMembershipWhenFinalIdentityCheckFails(self):
        with self.archive_service() as (_, archive):
            provider = JiraFixture(self, archive=archive)
            original = provider.respond
            identities = []

            def respond(path, params):
                if path.endswith('/myself'):
                    identities.append(path)
                    return 200, {'key': 'principal-1' if len(identities) == 1 else 'another-principal'}
                return original(path, params)

            provider.transport.responder = respond
            context = provider.context()
            receipt = ProjectCaptureService(provider.project_api, provider.service, archive).capture(context)
            self.assertEqual((False, True, 'PRINCIPAL_CHANGED'),
                             (receipt.complete, receipt.membership_complete, receipt.failure_code))
