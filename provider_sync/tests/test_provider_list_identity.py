from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import unittest
import uuid

from bug_metrics.app.api.provider_connections import ConnectionError, ProviderConnectionResolver
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from project_management.app.api import ProjectActor, ProjectError
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.app.api.access_contracts import AccessError, CaptureLimits, ProviderRequestContext
from provider_sync.app.api.list_identity import ProviderListIdentityResolver, ResolutionFailure
from provider_sync.tests.capture_gateway_fixtures import JiraFixture, issue


class TestProviderListIdentity(CaptureArchiveScenario, unittest.TestCase):
    def fixture(self):
        fixture = JiraFixture(self)
        fixture.rows.append(issue('102'))
        existing = fixture.respond

        def respond(path, params):
            if '/issue/' in path:
                key = path.rsplit('/', 1)[1]
                row = next((row for row in fixture.rows if key in (row['id'], row['key'])), None)
                if row:
                    return 200, {'id': row['id'], 'key': row['key'], 'fields': {'updated': row['fields']['updated']}}
            return existing(path, params)

        fixture.transport.responder = respond
        self.secret_reads = []
        reads = self.secret_reads

        class CountingResolver(ProviderConnectionResolver):
            def resolve_profile(inner, profile_id, **kwargs):
                reads.append(profile_id)
                return super().resolve_profile(profile_id, **kwargs)

            def describe_profile(inner, profile_id, **kwargs):
                info = super().describe_profile(profile_id, **kwargs)
                change = getattr(fixture, 'info_change', None)
                return change(info) if change else info

        resolver = ProviderListIdentityResolver(
            fixture.project_api, lambda: fixture.registry,
            lambda registry: CountingResolver(SimpleNamespace(), registry),
            reader_factory=fixture.reader_factory,
        )
        return fixture, resolver

    def context(self, **changes):
        context = ProviderRequestContext(self.actor, self.project.id, str(uuid.uuid4()),
                                         datetime.now(UTC) + timedelta(minutes=5), CaptureLimits())
        return replace(context, **changes)

    def resolve(self, resolver, *, context=None, identifiers=('ALPHA-101', '102'), **kwargs):
        arguments = {'profile_id': self.stage.descriptor.profile_id, 'provider_id': 'jira',
                     'expected_endpoint_url': self.stage.descriptor.endpoint, 'identifiers': identifiers, 'online': True}
        arguments.update(kwargs)
        return resolver.resolve(context or self.context(), **arguments)

    def test_shouldResolveKeysAndIdsUnderOnePrincipalAndBudget(self):
        fixture, resolver = self.fixture()
        result = self.resolve(resolver)
        self.assertEqual([('ALPHA-101', '101'), ('102', '102')],
                         [(row.requested, row.identity.stable_id) for row in result.bindings])
        self.assertEqual(('principal-1', 4, 1),
                         (result.principal.principal_id, result.usage.requests, len(self.secret_reads)))
        self.assertTrue(all(response.raw.closed for response in fixture.transport.responses))
        self.assertFalse(any(path.endswith('/search') for _, path, _ in fixture.transport.requests))

    def test_shouldRefuseOwnerArchiveOfflineAndUnsafeIdentifiersBeforeCredentials(self):
        cases = [
            ({'context': self.context(actor=ProjectActor('other-owner'))}, 'PROJECT_NOT_FOUND'),
            ({'online': False}, 'CAPABILITY_UNAVAILABLE'),
            ({'expected_endpoint_url': 'https://other.example/jira'}, 'PROVIDER_ENDPOINT_INVALID'),
            ({'identifiers': ('../search',)}, 'INVALID_ARGUMENTS'),
            ({'identifiers': ()}, 'INVALID_ARGUMENTS'),
            ({'identifiers': ('101', '101')}, 'INVALID_ARGUMENTS'),
            ({'provider_id': 'hsdes'}, 'PART_CONTRACT_UNQUALIFIED'),
        ]
        for arguments, code in cases:
            fixture, resolver = self.fixture()
            with self.subTest(code=code), self.assertRaises((AccessError, ProjectError)) as caught:
                self.resolve(resolver, **arguments)
            self.assertEqual((code, [], []), (caught.exception.code, self.secret_reads, fixture.transport.requests))
        fixture, resolver = self.fixture()
        fixture.project_api.project = replace(self.project, archived=True)
        with self.assertRaises(ProjectError) as caught:
            self.resolve(resolver)
        self.assertEqual(('PROJECT_ARCHIVED', []), (caught.exception.code, self.secret_reads))

    def test_shouldRejectDuplicateStableIdsAndWrongNumericIdentity(self):
        for inputs, code, index in [
            (('ALPHA-101', '101'), 'PROVIDER_DUPLICATE_ID', 1),
            (('999',), 'PROVIDER_RECORD_INVALID', 0),
        ]:
            fixture, resolver = self.fixture()
            original = fixture.transport.responder

            def respond(path, params):
                if path.endswith('/issue/999'):
                    return 200, {'id': '101', 'key': 'ALPHA-101', 'fields': {'updated': 'v1'}}
                return original(path, params)

            fixture.transport.responder = respond
            with self.subTest(code=code), self.assertRaises(ResolutionFailure) as caught:
                self.resolve(resolver, identifiers=inputs)
            self.assertEqual((code, index), (caught.exception.code, caught.exception.failed_index))
            self.assertFalse(hasattr(caught.exception, 'bindings'))
            self.assertEqual(len(fixture.transport.requests), caught.exception.usage.requests)

    def test_shouldRefuseChangedPrincipalAndProfileAtCompletion(self):
        for change in ('principal', 'profile'):
            fixture, resolver = self.fixture()
            original = fixture.transport.responder
            calls = []

            def respond(path, params):
                response = original(path, params)
                if path.endswith('/myself'):
                    calls.append(path)
                    if len(calls) == 2:
                        if change == 'principal':
                            return 200, {'key': 'different-principal'}
                        fixture.registry = ProjectProviderProfileRegistry.from_records([])
                return response

            fixture.transport.responder = respond
            with self.subTest(change=change), self.assertRaises(ResolutionFailure) as caught:
                self.resolve(resolver)
            self.assertEqual('PRINCIPAL_CHANGED' if change == 'principal' else 'SOURCE_CHANGED', caught.exception.code)
            self.assertEqual((4, None, 1),
                             (caught.exception.usage.requests, caught.exception.failed_index, len(self.secret_reads)))
            self.assertTrue(all(response.raw.closed for response in fixture.transport.responses))

    def test_shouldRejectFinalConnectionMetadataDriftWithoutResolvingAnotherSecret(self):
        changes = [
            lambda info: replace(info, endpoint=replace(info.endpoint, base_url='https://other.example/jira')),
            lambda info: replace(info, endpoint=replace(info.endpoint, auth_mode='cloud_basic')),
            lambda info: replace(info, endpoint=replace(info.endpoint, transport='other-transport')),
            lambda info: replace(info, endpoint=replace(info.endpoint, tls=replace(info.endpoint.tls, verification=False))),
            lambda info: replace(info, credential=replace(info.credential, kind='protected')),
            lambda info: replace(info, credential=replace(info.credential, reference='other-selection')),
            lambda info: replace(info, credential=replace(info.credential, revision='next-revision')),
        ]
        for change in changes:
            fixture, resolver = self.fixture()
            original = fixture.transport.responder
            probes = []

            def respond(path, params):
                response = original(path, params)
                if path.endswith('/myself'):
                    probes.append(path)
                    if len(probes) == 2:
                        fixture.info_change = change
                return response

            fixture.transport.responder = respond
            with self.subTest(change=change), self.assertRaises(ResolutionFailure) as caught:
                self.resolve(resolver)
            self.assertEqual(('SOURCE_CHANGED', None, 4, 1),
                             (caught.exception.code, caught.exception.failed_index,
                              caught.exception.usage.requests, len(self.secret_reads)))
            self.assertTrue(all(response.raw.closed for response in fixture.transport.responses))

    def test_shouldCountProbesAndFailuresAgainstTheOriginalBudget(self):
        fixture, resolver = self.fixture()
        with self.assertRaises(ResolutionFailure) as caught:
            self.resolve(resolver, context=self.context(limits=CaptureLimits(max_requests=2)))
        self.assertEqual(('CAPTURE_REQUEST_LIMIT', 2, 1),
                         (caught.exception.code, caught.exception.usage.requests, caught.exception.failed_index))
        self.assertEqual(2, len(fixture.transport.requests))

    def test_shouldPreserveCredentialAndConfigurationFailureCategories(self):
        for code in ('PROVIDER_CREDENTIAL_INVALID', 'PROVIDER_CREDENTIAL_UNAVAILABLE',
                     'PROVIDER_PROFILE_UNAVAILABLE', 'PROVIDER_TRUST_INVALID', 'PROVIDER_UNSUPPORTED'):
            fixture, resolver = self.fixture()

            class RefusingResolver(ProviderConnectionResolver):
                def resolve_profile(inner, profile_id, **kwargs):
                    raise ConnectionError(code)

            resolver.resolver_factory = lambda registry: RefusingResolver(SimpleNamespace(), registry)
            with self.subTest(code=code), self.assertRaises(ResolutionFailure) as caught:
                self.resolve(resolver)
            self.assertEqual((code, 0, None, []),
                             (caught.exception.code, caught.exception.usage.requests,
                              caught.exception.failed_index, fixture.transport.requests))
