from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import unittest
import uuid

from project_management.app.api import ProjectActor, ProjectError
from project_management.app.api.capture_archive import CaptureIntent, CaptureSourceIdentity, RawPageRef
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario, ProjectApiStub
from provider_sync.app.api.access import ProviderAccessService
from provider_sync.app.api.access_contracts import AccessContext, AccessError, CaptureLimits
from provider_sync.app.spi.capture import ArchivePageSink, RawResponse
from provider_sync.services.capture_session import CaptureSession


class RejectingResolver:
    def __init__(self):
        self.requests = []

    def resolve_profile(self, profile_id, **kwargs):
        self.requests.append(profile_id)
        raise AssertionError('A refused project must not read credentials.')


class ScriptedReader:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.closed = False

    def read(self, path, params, *, timeout, max_bytes):
        self.requests.append((path, params, timeout, max_bytes))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def context_for(case, **changes):
    value = AccessContext(
        case.actor, case.project.id, case.stage.id, str(uuid.uuid4()), str(uuid.uuid4()),
        datetime.now(UTC) + timedelta(minutes=5), CaptureLimits(),
    )
    return replace(value, **changes)


class TestProviderCaptureAccess(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldRefuseUnqualifiedHsdBeforeOpeningAnyJiraConnection(self):
        resolver = RejectingResolver()
        descriptor = replace(self.stage.descriptor, provider_id='hsdes', query_kind='saved_query')
        stage = replace(self.stage, descriptor=descriptor, definition_hash=descriptor.definition_hash())
        service = ProviderAccessService(ProjectApiStub(self.project, stage), resolver, {}, None)
        with self.assertRaises(AccessError) as caught:
            service.open_capture(context_for(self), online=True)
        self.assertEqual(('PART_CONTRACT_UNQUALIFIED', []), (caught.exception.code, resolver.requests))

    def test_shouldRefuseOtherOwnerBeforeResolvingConnection(self):
        resolver = RejectingResolver()
        service = ProviderAccessService(ProjectApiStub(self.project, self.stage), resolver, {}, None)
        with self.assertRaises(ProjectError) as caught:
            service.open_capture(context_for(self, actor=ProjectActor('other-owner')), online=True)
        self.assertEqual(('PROJECT_NOT_FOUND', []), (caught.exception.code, resolver.requests))

    def test_shouldRefuseArchivedOrChangedStageBeforeResolvingConnection(self):
        for archived, status, code in [
            (True, 'current', 'PROJECT_ARCHIVED'),
            (False, 'source_changed', 'SOURCE_CHANGED'),
            (False, 'unavailable', 'SOURCE_UNAVAILABLE'),
        ]:
            with self.subTest(code=code):
                resolver = RejectingResolver()
                project = replace(self.project, archived=archived)
                stage = replace(self.stage, source_status=status)
                service = ProviderAccessService(ProjectApiStub(project, stage), resolver, {}, None)
                with self.assertRaises(ProjectError) as caught:
                    service.open_capture(context_for(self), online=True)
                self.assertEqual((code, []), (caught.exception.code, resolver.requests))

    def test_shouldRequireExplicitOnlineAccessAndValidDeadline(self):
        resolver = RejectingResolver()
        service = ProviderAccessService(ProjectApiStub(self.project, self.stage), resolver, {}, None)
        for context, online, code in [
            (context_for(self), False, 'CAPABILITY_UNAVAILABLE'),
            (context_for(self, deadline_at=datetime.now(UTC) - timedelta(seconds=1)), True, 'CAPTURE_DEADLINE_EXPIRED'),
            (context_for(self, capture_id='../elsewhere'), True, 'INVALID_ARGUMENTS'),
        ]:
            with self.subTest(code=code), self.assertRaises(AccessError) as caught:
                service.open_capture(context, online=online)
            self.assertEqual(code, caught.exception.code)
        self.assertEqual([], resolver.requests)


class TestCaptureSession(CaptureArchiveScenario, unittest.TestCase):
    def session(self, responses, *, limits=None):
        context = context_for(self, limits=limits or CaptureLimits())
        reader = ScriptedReader(*responses)
        session = CaptureSession(context, reader, timeout_seconds=30)
        source = CaptureSourceIdentity('jira', 'alpha-endpoint', self.stage.descriptor.endpoint,
                                       'principal-1', 'revision-1', self.stage.definition_hash)
        intent = CaptureIntent(context.project_id, context.stage_id, context.capture_id,
                               context.request_id, source, 'a' * 64, ('facts', 'comments'),
                               context.deadline_at)
        captured = []

        def append(page):
            captured.append(page)
            return RawPageRef(hashlib.sha256(page.page_key.encode()).hexdigest(),
                              hashlib.sha256(page.payload).hexdigest(), len(page.payload),
                              page.content_type, page.request_fingerprint)

        return session, reader, ArchivePageSink(intent, append), captured

    def test_shouldFlushHeldIdentityBeforeNewPagesAndRejectSecondAttachment(self):
        session, reader, sink, pages = self.session([
            RawResponse(200, 'application/json', b'{"key":"principal-1"}', False, None),
            RawResponse(200, 'application/json', b'{"issues":[]}', False, None),
        ])
        first = session.get_json('/rest/api/2/myself', {}, page_key='identity')
        self.assertIsNone(first.raw_page_id)
        session.attach_archive_sink(sink)
        second = session.get_json('/rest/api/2/search', {}, page_key='membership')
        with self.assertRaises(AccessError) as caught:
            session.attach_archive_sink(sink)
        self.assertEqual(('CAPTURE_SINK_CONFLICT', ['identity', 'membership'], 2),
                         (caught.exception.code, [p.page_key for p in pages], session.usage.requests))
        self.assertIsNotNone(second.raw_page_id)
        session.close()
        self.assertTrue(reader.closed)

    def test_shouldRefuseSinkBoundToAnotherCaptureBeforeFlushing(self):
        session, _, sink, pages = self.session([
            RawResponse(200, 'application/json', b'{}', False, None),
        ])
        session.get_json('/rest/api/2/myself', {}, page_key='identity')
        with self.assertRaises(AccessError) as caught:
            session.attach_archive_sink(replace(sink, intent=replace(sink.intent, capture_id=str(uuid.uuid4()))))
        self.assertEqual(('CAPTURE_SINK_CONFLICT', []), (caught.exception.code, pages))

    def test_shouldRetainFailedBodyBeforeRejectingIt(self):
        cases = [
            (RawResponse(200, 'application/json', b'{"a":1,"a":2}', False, None), 'PROVIDER_RESPONSE_INVALID'),
            (RawResponse(200, 'application/json', b'{"a":NaN}', False, None), 'PROVIDER_RESPONSE_INVALID'),
            (RawResponse(200, 'application/json', b'{"a":1e999}', False, None), 'PROVIDER_RESPONSE_INVALID'),
            (RawResponse(200, 'application/json', b'[]', False, None), 'PROVIDER_RESPONSE_INVALID'),
            (RawResponse(403, 'application/json', b'{"message":"no access"}', False, None), 'PROVIDER_PERMISSION_DENIED'),
            (RawResponse(200, 'application/json', b'{"partial":', True, 'CAPTURE_RESPONSE_LIMIT'), 'CAPTURE_RESPONSE_LIMIT'),
        ]
        for response, code in cases:
            with self.subTest(code=code, body=response.body):
                session, _, sink, pages = self.session([response])
                session.attach_archive_sink(sink)
                with self.assertRaises(AccessError) as caught:
                    session.get_json('/rest/api/2/search', {}, page_key='failed')
                self.assertEqual((code, response.body, response.partial),
                                 (caught.exception.code, pages[0].payload, pages[0].partial))

    def test_shouldChargeFailedRequestsAndStopBeforeAnotherSend(self):
        session, reader, sink, pages = self.session([
            RawResponse(429, 'application/json', b'{}', False, None),
        ], limits=CaptureLimits(max_requests=1))
        session.attach_archive_sink(sink)
        with self.assertRaises(AccessError):
            session.get_json('/rest/api/2/search', {}, page_key='first')
        with self.assertRaises(AccessError) as caught:
            session.get_json('/rest/api/2/search', {}, page_key='second')
        self.assertEqual(('CAPTURE_REQUEST_LIMIT', 1, 2, 1),
                         (caught.exception.code, len(reader.requests), session.usage.downloaded_bytes, len(pages)))

    def test_shouldRejectClosedSessionWithoutSending(self):
        session, reader, _, _ = self.session([])
        session.close()
        with self.assertRaises(AccessError) as caught:
            session.get_json('/rest/api/2/myself', {}, page_key='late')
        self.assertEqual(('CAPTURE_CLOSED', []), (caught.exception.code, reader.requests))
