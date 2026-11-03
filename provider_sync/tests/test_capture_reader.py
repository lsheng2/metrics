import unittest

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.app.api.access_contracts import AccessError
from provider_sync.tests.capture_gateway_fixtures import JiraFixture


class TestBoundCaptureReader(CaptureArchiveScenario, unittest.TestCase):
    def reader(self, fixture):
        handle = fixture.resolver.resolve_profile(self.stage.descriptor.profile_id)
        reader = handle.open_capture_reader(fixture.reader_factory)
        self.addCleanup(reader.close)
        return reader

    def test_shouldKeepBoundedPrefixWhenResponseExceedsLimit(self):
        fixture = JiraFixture(self, responder=lambda path, params: (200, b'{"body":"too much data"}'))
        result = self.reader(fixture).read('/rest/api/2/myself', {}, timeout=5, max_bytes=8)
        self.assertEqual((b'{"body":', True, 'CAPTURE_RESPONSE_LIMIT'),
                         (result.body, result.partial, result.error_code))
        self.assertTrue(fixture.transport.responses[0].raw.closed)

    def test_shouldAcceptExactUnencodedContentLengthWithoutReadingExtraBytes(self):
        fixture = JiraFixture(self, responder=lambda path, params: (200, b'{}'))
        result = self.reader(fixture).read('/rest/api/2/myself', {}, timeout=5, max_bytes=2)
        self.assertEqual((b'{}', False, None), (result.body, result.partial, result.error_code))

    def test_shouldRetainRedirectBodyWithoutFollowingAnotherEndpoint(self):
        fixture = JiraFixture(self, responder=lambda path, params: (302, b'{"error":"redirect"}'))
        result = self.reader(fixture).read('/rest/api/2/myself', {}, timeout=5, max_bytes=1024)
        self.assertEqual((302, b'{"error":"redirect"}', 1),
                         (result.status_code, result.body, len(fixture.transport.requests)))
        self.assertTrue(fixture.transport.responses[0].raw.closed)

    def test_shouldRefuseArbitraryPathsBeforeSendingCredentials(self):
        fixture = JiraFixture(self)
        reader = self.reader(fixture)
        for path in ('https://elsewhere.example/rest/api/2/myself', '/rest/api/2/issue/101/worklog',
                     '/rest/api/2/issue/../search', '/rest/api/2/issue/ALPHA-101/comment',
                     '/rest/api/2/issue/ALPHA-101%2fworklog'):
            with self.subTest(path=path), self.assertRaises(AccessError):
                reader.read(path, {}, timeout=5, max_bytes=1024)
        self.assertEqual([], fixture.transport.requests)

    def test_shouldAllowOnlyTheIssueReadPathForAJiraKey(self):
        fixture = JiraFixture(self, responder=lambda path, params: (200, b'{"id":"101","key":"ALPHA-101"}'))
        result = self.reader(fixture).read('/rest/api/2/issue/ALPHA-101', {'fields': 'id,key,updated'},
                                          timeout=5, max_bytes=1024)
        self.assertEqual((200, b'{"id":"101","key":"ALPHA-101"}', False),
                         (result.status_code, result.body, result.partial))
        self.assertEqual([('GET', '/jira/rest/api/2/issue/ALPHA-101', {'fields': 'id,key,updated'})],
                         fixture.transport.requests)
        self.assertTrue(fixture.transport.responses[0].raw.closed)
