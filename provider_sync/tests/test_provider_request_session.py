from dataclasses import replace
from datetime import UTC, datetime, timedelta
import unittest
import uuid

from project_management.app.api import ProjectActor
from provider_sync.app.api.access_contracts import AccessError, CaptureLimits, ProviderRequestContext
from provider_sync.app.spi.capture import RawResponse
from provider_sync.services.capture_session import CaptureSession, ProviderReadSession
from provider_sync.tests.test_provider_capture_gateway import ScriptedReader


class TestProviderRequestSession(unittest.TestCase):
    def context(self, **changes):
        context = ProviderRequestContext(ProjectActor('reader'), str(uuid.uuid4()), str(uuid.uuid4()),
                                         datetime.now(UTC) + timedelta(minutes=5), CaptureLimits())
        return replace(context, **changes)

    def test_shouldUseAProjectRequestWithoutCreatingStageOrCaptureIdentity(self):
        reader = ScriptedReader(RawResponse(200, 'application/json', b'{"id":"101"}', False, None))
        session = ProviderReadSession(self.context(limits=CaptureLimits(max_requests=1)), reader, timeout_seconds=30)
        self.addCleanup(session.close)
        result = session.get_json('/rest/api/2/issue/ALPHA-1', {}, page_key='item-1')
        self.assertEqual({'id': '101'}, result.value)
        self.assertIsNone(result.raw_page_id)
        self.assertFalse(hasattr(session, 'attach_archive_sink'))
        with self.assertRaises(AccessError) as caught:
            session.get_json('/rest/api/2/myself', {}, page_key='final')
        self.assertEqual(('CAPTURE_REQUEST_LIMIT', 1), (caught.exception.code, len(reader.requests)))
        session.close()
        self.assertTrue(reader.closed)

    def test_shouldRefuseProjectOnlyContextForArchiveCapture(self):
        reader = ScriptedReader()
        with self.assertRaises(AccessError) as caught:
            CaptureSession(self.context(), reader, timeout_seconds=30)
        self.assertEqual(('INVALID_ARGUMENTS', []), (caught.exception.code, reader.requests))

    def test_shouldHonorDeadlineDownloadAndFailedRequestAccounting(self):
        reader = ScriptedReader(RawResponse(403, 'application/json', b'{}', False, None))
        clock = [datetime.now(UTC)]
        ticks = [10.0]
        session = ProviderReadSession(
            self.context(limits=CaptureLimits(max_download_bytes=2)), reader, timeout_seconds=30,
            clock=lambda: clock[0], monotonic=lambda: ticks[0],
        )
        self.addCleanup(session.close)
        with self.assertRaises(AccessError):
            session.get_json('/rest/api/2/myself', {}, page_key='denied')
        with self.assertRaises(AccessError) as caught:
            session.get_json('/rest/api/2/myself', {}, page_key='another')
        self.assertEqual(('CAPTURE_DOWNLOAD_LIMIT', 1, 2),
                         (caught.exception.code, session.usage.requests, session.usage.downloaded_bytes))
        ticks[0] += 600
        with self.assertRaises(AccessError) as caught:
            session.get_json('/rest/api/2/myself', {}, page_key='expired')
        self.assertEqual(('CAPTURE_DEADLINE_EXPIRED', 1), (caught.exception.code, len(reader.requests)))

    def test_shouldRejectMalformedProjectRequestBeforeSending(self):
        for change in [{'project_id': '../escape'}, {'request_id': 'invalid'},
                       {'actor': ProjectActor(' ')}, {'deadline_at': datetime(2026, 11, 2)}]:
            with self.subTest(change=change), self.assertRaises(AccessError):
                ProviderReadSession(self.context(**change), ScriptedReader(), timeout_seconds=30)

    def test_shouldCarryProviderStatusAndRetryAfterForSingleItemReads(self):
        reader = ScriptedReader(RawResponse(429, 'application/json', b'{}', False, None, retry_after='7'))
        session = ProviderReadSession(self.context(), reader, timeout_seconds=30)
        self.addCleanup(session.close)

        with self.assertRaises(AccessError) as caught:
            session.get_json('/rest/api/2/issue/ALPHA-1', {}, page_key='rate-limited')

        self.assertEqual('PROVIDER_RATE_LIMITED', caught.exception.code)
        self.assertEqual(429, caught.exception.provider_status)
        self.assertEqual(7, caught.exception.retry_after_seconds)
