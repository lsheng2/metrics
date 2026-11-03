import unittest

from project_management.services.capture import ProjectCaptureService
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.app.api.access_contracts import AccessError
from provider_sync.tests.capture_gateway_fixtures import JiraFixture


class TestCaptureCancellation(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldRefuseBeforeOpeningProviderConnectionWhenCancelIsAlreadyRequested(self):
        with self.archive_service() as (root, archive):
            provider = JiraFixture(self, archive=archive)
            capture = ProjectCaptureService(provider.project_api, provider.service, archive)
            context = provider.context()
            with self.assertRaises(AccessError) as caught:
                capture.capture(context, cancel_requested=lambda: True)
            self.assertEqual(('CAPTURE_CANCELED', [], 0),
                             (caught.exception.code, provider.transport.requests,
                              int(self.archive_path(root).exists())))

    def test_shouldSealRetainedPagesWhenCancelArrivesBetweenCommentPages(self):
        with self.archive_service() as (_, archive):
            provider = JiraFixture(self, archive=archive)

            def cancel_after_first_comment_page():
                return any(path.endswith('/comment') and params.get('startAt') == '0'
                           for _, path, params in provider.transport.requests)

            capture = ProjectCaptureService(provider.project_api, provider.service, archive)
            context = provider.context()
            receipt = capture.capture(context, cancel_requested=cancel_after_first_comment_page)
            snapshot = provider.service.read_item(self.actor, self.project.id, self.stage.id,
                                                  context.capture_id, '101')
            comment_pages = [(path, params.get('startAt')) for _, path, params in provider.transport.requests
                             if path.endswith('/comment')]
            self.assertEqual((False, 'CAPTURE_CANCELED', ['201', '202'], [('/jira/rest/api/2/issue/101/comment', '0')]),
                             (receipt.complete, receipt.failure_code,
                              list(snapshot.comments_by_id), comment_pages))
