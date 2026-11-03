from dataclasses import replace
import unittest

from project_management.app.api import ProjectError
from project_management.app.api.capture_archive import CaptureIntent
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.app.api.access_contracts import AccessError, CaptureLimits
from provider_sync.app.spi.capture import ArchivePageSink
from provider_sync.tests.capture_gateway_fixtures import JiraFixture, attach_sink, issue, page


class TestJiraCapture(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldReuseAlreadyResolvedFilterAtUniqueDefinitionLimit(self):
        query = 'filter IN (' + ','.join(str(index) for index in range(1, 129)) + ')'
        fixture = JiraFixture(self, query=query)
        fixture.filters = {str(index): 'filter = 1' for index in range(1, 129)}
        fixture.filters['1'] = 'project = ALPHA'
        with fixture.service.open_capture(fixture.context(limits=CaptureLimits(max_requests=1024)), online=True) as lease:
            self.assertEqual(128, len(lease.resolved_scope.dependencies))

    def test_shouldApplyStoredSourceBindingToOnlineDiagnosticsToo(self):
        fixture = JiraFixture(self)
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            original = lease.resolved_scope

        class StoredResolution:
            def read_source_resolution(self, actor, project_id, stage_id):
                return original

        fixture.service.archive = StoredResolution()
        fixture.principal = 'different-principal'
        with self.assertRaises(ProjectError) as caught:
            fixture.service.open_capture(fixture.context(), online=True)
        self.assertEqual('SOURCE_CHANGED', caught.exception.code)

    def test_shouldNotAcceptBooleanAsSavedFilterIdentity(self):
        fixture = JiraFixture(self, query='filter = 1')
        fixture.filters = {'1': 'project = ALPHA'}
        original = fixture.respond

        def respond(path, params):
            if path.endswith('/filter/1'):
                return 200, {'id': True, 'jql': 'project = ALPHA'}
            return original(path, params)

        fixture.transport.responder = respond
        with self.assertRaises(AccessError) as caught:
            fixture.service.open_capture(fixture.context(), online=True)
        self.assertEqual('SCOPE_UNVERIFIABLE', caught.exception.code)

    def test_shouldUseConnectionNormalizationWithoutRewritingFrozenEndpoint(self):
        endpoint = 'https://TRACKER.EXAMPLE.TEST:443/jira/'
        descriptor = replace(self.stage.descriptor, endpoint=endpoint)
        self.stage = replace(self.stage, descriptor=descriptor, definition_hash=descriptor.definition_hash())
        fixture = JiraFixture(self)
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            self.assertEqual(endpoint, lease.source_identity.endpoint_url)
            self.assertTrue(all(path.startswith('/jira/rest/') for _, path, _ in fixture.transport.requests))

    def test_shouldBoundDetailAttemptsAndRequireArchiveBeforeReadingDetails(self):
        fixture = JiraFixture(self)
        fixture.rows.append(issue('102'))
        with fixture.service.open_capture(fixture.context(limits=CaptureLimits(max_details=1)), online=True) as lease:
            markers = lease.enumerate().members
            with self.assertRaises(AccessError) as caught:
                lease.capture_item(markers[0])
            self.assertEqual('CAPTURE_SINK_CONFLICT', caught.exception.code)
            attach_sink(lease)
            lease.capture_item(markers[0])
            count = len(fixture.transport.requests)
            with self.assertRaises(AccessError) as caught:
                lease.capture_item(markers[1])
            self.assertEqual(('CAPTURE_DETAILS_PENDING', count),
                             (caught.exception.code, len(fixture.transport.requests)))

    def test_shouldReadClosedItemAndEveryAddedCommentThroughOneBoundLease(self):
        fixture = JiraFixture(self)
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            raw = attach_sink(lease)
            membership = lease.enumerate()
            observation = lease.capture_item(membership.members[0])
            lease.verify_final()
            self.assertEqual(('complete', ['201', '202', '203'], ['A', 'B', 'C'], True),
                             (observation.coverage.comments.state,
                              list(observation.snapshot.comments_by_id),
                              [c['body'] for c in observation.snapshot.comments_by_id.values()],
                              observation.snapshot.consistent))
            self.assertEqual(len(fixture.transport.requests), lease.usage.requests)
            self.assertEqual(len(fixture.transport.responses), len(raw))
        self.assertTrue(all(response.raw.closed for response in fixture.transport.responses))

    def test_shouldKeepPartialCommentRecordsAndFailedResponse(self):
        fixture = JiraFixture(self)
        original = fixture.respond

        def respond(path, params):
            if path.endswith('/comment') and params['startAt'] == '2':
                return 403, {'errorMessages': ['No longer visible.']}
            return original(path, params)

        fixture.transport.responder = respond
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            raw = attach_sink(lease)
            marker = lease.enumerate().members[0]
            observed = lease.capture_item(marker)
            self.assertEqual(('partial', ['201', '202'], 'PROVIDER_PERMISSION_DENIED'),
                             (observed.coverage.comments.state, list(observed.snapshot.comments_by_id),
                              observed.coverage.comments.reason_code))
            self.assertTrue(any(b'No longer visible' in value.payload for value in raw))

    def test_shouldRefuseChangingTotalsDuplicateIdsAndMemberOverflow(self):
        for kind, expected in [('total', 'PROVIDER_PAGE_INVALID'),
                               ('duplicate', 'PROVIDER_DUPLICATE_ID'),
                               ('limit', 'PROVIDER_RECORD_LIMIT')]:
            with self.subTest(kind=kind):
                fixture = JiraFixture(self)
                fixture.rows = [issue('101'), issue('102'), issue('103')]
                original = fixture.respond

                def respond(path, params):
                    if path.endswith('/search') and params.get('startAt') == '2':
                        if kind == 'total':
                            return 200, page([issue('103')], 2, 4)
                        if kind == 'duplicate':
                            return 200, page([issue('101')], 2, 3)
                    return original(path, params)

                fixture.transport.responder = respond
                limits = CaptureLimits(page_size=2, max_members=2 if kind == 'limit' else 500)
                with fixture.service.open_capture(fixture.context(limits=limits), online=True) as lease:
                    attach_sink(lease)
                    result = lease.enumerate()
                    self.assertEqual(('partial', expected), (result.coverage.state, result.coverage.reason_code))

    def test_shouldPreserveBothDetailVersionsWithoutClaimingConsistency(self):
        fixture = JiraFixture(self)
        original = fixture.respond
        calls = []

        def respond(path, params):
            if path.endswith('/issue/101'):
                calls.append(path)
                return 200, issue(description='before' if len(calls) == 1 else 'after')
            return original(path, params)

        fixture.transport.responder = respond
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            raw = attach_sink(lease)
            result = lease.capture_item(lease.enumerate().members[0])
            self.assertFalse(result.snapshot.consistent)
            self.assertEqual('before', result.snapshot.facts['description'])
            self.assertTrue(any(b'after' in p.payload for p in raw))

    def test_shouldDetectPrincipalAndMembershipDriftAtFinalCheck(self):
        for change, code in [('principal', 'PRINCIPAL_CHANGED'), ('membership', 'SOURCE_UNSTABLE')]:
            with self.subTest(change=change):
                fixture = JiraFixture(self)
                with fixture.service.open_capture(fixture.context(), online=True) as lease:
                    attach_sink(lease)
                    lease.enumerate()
                    if change == 'principal':
                        fixture.principal = 'someone-else'
                    else:
                        fixture.rows.append(issue('999'))
                    with self.assertRaises(AccessError) as caught:
                        lease.verify_final()
                    self.assertEqual(code, caught.exception.code)

    def test_shouldRejectNestedFilterCyclesAndUnqualifiedFunctions(self):
        for query, filters in [
            ('filter = 12', {'12': 'filter = 13', '13': 'filter = 12'}),
            ('assignee = currentUser()', {}),
        ]:
            with self.subTest(query=query):
                fixture = JiraFixture(self, query=query)
                fixture.filters = filters
                with self.assertRaises(AccessError) as caught:
                    fixture.service.open_capture(fixture.context(), online=True)
                self.assertEqual('SCOPE_UNVERIFIABLE', caught.exception.code)
                self.assertTrue(all(response.raw.closed for response in fixture.transport.responses))

    def test_shouldRefuseLaterFilterDefinitionDrift(self):
        fixture = JiraFixture(self, query='filter = 12')
        fixture.filters = {'12': 'project = ALPHA'}
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            attach_sink(lease)
            lease.enumerate()
            fixture.filters['12'] = 'project = BETA'
            with self.assertRaises(AccessError) as caught:
                lease.verify_final()
            self.assertEqual('SOURCE_CHANGED', caught.exception.code)

    def test_shouldKeepHistoryPartialWhenExpansionIsTruncated(self):
        fixture = JiraFixture(self)
        fixture.rows[0]['changelog']['total'] = 3
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            attach_sink(lease)
            result = lease.capture_item(lease.enumerate().members[0])
            self.assertEqual(('partial', 0, 3),
                             (result.coverage.history.state, result.coverage.history.observed_count,
                              result.coverage.history.total_count))
            self.assertFalse(any('/changelog' in path for _, path, _ in fixture.transport.requests))

    def test_shouldRefuseWrongSinkPrincipalAndWrongItemEndpoint(self):
        fixture = JiraFixture(self)
        with fixture.service.open_capture(fixture.context(), online=True) as lease:
            context = lease.context
            wrong = replace(lease.source_identity, principal_id='someone-else')
            intent = CaptureIntent(context.project_id, context.stage_id, context.capture_id,
                                   context.request_id, wrong, 'a' * 64, ('facts',), context.deadline_at)
            with self.assertRaises(AccessError) as caught:
                lease.attach_archive_sink(ArchivePageSink(intent, lambda page: None))
            self.assertEqual('CAPTURE_SINK_CONFLICT', caught.exception.code)
            attach_sink(lease)
            marker = lease.enumerate().members[0]
            wrong_marker = replace(marker, identity=replace(marker.identity, endpoint_id='another-site'))
            before = len(fixture.transport.requests)
            with self.assertRaises(AccessError):
                lease.capture_item(wrong_marker)
            self.assertEqual(before, len(fixture.transport.requests))
