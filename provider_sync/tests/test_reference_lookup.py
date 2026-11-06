from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import unittest
import uuid

from project_management.app.api import ProjectActor
from project_management.app.api.capture_archive import WorkItemIdentity
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.app.api.access_contracts import AccessError
from provider_sync.app.api.references import (
    ADAPTER_REVISION,
    DisabledProviderReferenceReader,
    JiraProviderReferenceReader,
    ProviderReferenceObservation,
    create_provider_reference_reader,
)
from provider_sync.tests.capture_gateway_fixtures import JiraFixture, issue


class TestJiraReferenceLookup(CaptureArchiveScenario, unittest.TestCase):
    def build_reader(self, fixture):
        info = fixture.resolver.describe_profile(fixture.stage.descriptor.profile_id, expected_provider_id='jira')
        return JiraProviderReferenceReader(
            fixture.resolver,
            ({
                'profile_id': fixture.stage.descriptor.profile_id,
                'provider_id': 'jira',
                'endpoint_id': info.endpoint.endpoint_id,
                'auth_mode': info.endpoint.auth_mode,
                'principal_id': 'principal-1',
                'adapter_revision': ADAPTER_REVISION,
                'qualification_ref': 'approved-reference-reader',
            },),
            clock=lambda: datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
            reader_factory=fixture.reader_factory,
        )

    def context(self, fixture):
        return {
            'actor': self.actor.subject,
            'actor_object': self.actor,
            'project_id': self.project.id,
            'stage_id': fixture.stage.id,
            'frozen_descriptor': fixture.stage.descriptor,
            'principal_id': 'principal-1',
            'rule_hash': fixture.stage.definition_hash,
            'membership_proof_hash': 'b' * 64,
            'deadline_at': datetime.now(UTC) + timedelta(seconds=10),
            'request_id': str(uuid.uuid4()),
        }

    def test_shouldVerifyPrincipalBeforeMinimalIssueGetAndAllowJiraKeyRename(self):
        fixture = JiraFixture(self)
        fixture.rows = [issue('101')]
        fixture.rows[0]['key'] = 'ALPHA-RENAMED'
        reader = self.build_reader(fixture)
        member = WorkItemIdentity('jira', 'alpha-endpoint', '101', 'ALPHA-OLD')

        observed = reader.read(self.context(fixture), member)

        self.assertIsInstance(observed, ProviderReferenceObservation)
        self.assertEqual(('ALPHA-OLD', 'ALPHA-RENAMED', '101'), (
            observed.requested_key,
            observed.current_key,
            observed.identity.stable_id,
        ))
        self.assertEqual([
            ('GET', '/jira/rest/api/2/myself', {}),
            ('GET', '/jira/rest/api/2/issue/101', {'fields': 'summary,assignee,updated'}),
        ], fixture.transport.requests)

    def test_shouldStopBeforeItemReadWhenPrincipalDiffers(self):
        fixture = JiraFixture(self)
        fixture.principal = 'different-principal'
        reader = self.build_reader(fixture)

        with self.assertRaises(AccessError) as caught:
            reader.read(self.context(fixture), WorkItemIdentity('jira', 'alpha-endpoint', '101', 'ALPHA-101'))

        self.assertEqual('PRINCIPAL_CHANGED', caught.exception.code)
        self.assertEqual([('GET', '/jira/rest/api/2/myself', {})], fixture.transport.requests)

    def test_shouldRejectWrongStableIdEvenWhenReturnedKeyMatches(self):
        def responder(path, params):
            if path == '/jira/rest/api/2/myself':
                return 200, {'key': 'principal-1', 'name': 'read-user'}
            if path == '/jira/rest/api/2/issue/101':
                row = issue('999')
                row['key'] = 'ALPHA-101'
                return 200, row
            raise AssertionError(f'unexpected path {path}')

        fixture = JiraFixture(self, responder=responder)
        reader = self.build_reader(fixture)

        with self.assertRaises(AccessError) as caught:
            reader.read(self.context(fixture), WorkItemIdentity('jira', 'alpha-endpoint', '101', 'ALPHA-101'))

        self.assertEqual('PROVIDER_RESPONSE_INVALID', caught.exception.code)

    def test_shouldDistinguishMissingNullAndMalformedAssigneeAndRejectBadUpdated(self):
        cases = [
            ({}, 'unknown', None),
            ({'assignee': None}, 'unassigned', None),
            ({'assignee': {'displayName': 12}}, 'unknown', None),
            ({'updated': 'not-a-time'}, None, 'PROVIDER_RESPONSE_INVALID'),
        ]
        for fields, expected_state, expected_error in cases:
            with self.subTest(fields=fields):
                def responder(path, params):
                    if path == '/jira/rest/api/2/myself':
                        return 200, {'key': 'principal-1', 'name': 'read-user'}
                    if path == '/jira/rest/api/2/issue/101':
                        row = issue('101')
                        row['fields'].pop('assignee', None)
                        row['fields'].update(fields)
                        return 200, row
                    raise AssertionError(f'unexpected path {path}')

                fixture = JiraFixture(self, responder=responder)
                reader = self.build_reader(fixture)
                if expected_error:
                    with self.assertRaises(AccessError) as caught:
                        reader.read(self.context(fixture), WorkItemIdentity('jira', 'alpha-endpoint', '101', 'ALPHA-101'))
                    self.assertEqual(expected_error, caught.exception.code)
                else:
                    observed = reader.read(self.context(fixture), WorkItemIdentity('jira', 'alpha-endpoint', '101', 'ALPHA-101'))
                    self.assertEqual(expected_state, observed.assignee_state)

    def test_factory_shouldStayDisabledByDefaultAndEnableOnlyQualifiedJiraRows(self):
        fixture = JiraFixture(self)
        info = fixture.resolver.describe_profile(fixture.stage.descriptor.profile_id, expected_provider_id='jira')
        disabled = create_provider_reference_reader(SimpleNamespace(
            METRICS_REPORT_COMPLETION_ENABLED=False,
            METRICS_REPORT_REFERENCE_QUALIFICATIONS=[],
        ), resolver=fixture.resolver)
        enabled = create_provider_reference_reader(SimpleNamespace(
            METRICS_REPORT_COMPLETION_ENABLED=True,
            METRICS_REPORT_REFERENCE_QUALIFICATIONS=[{
                'profile_id': fixture.stage.descriptor.profile_id,
                'provider_id': 'jira',
                'endpoint_id': info.endpoint.endpoint_id,
                'auth_mode': info.endpoint.auth_mode,
                'principal_id': 'principal-1',
                'adapter_revision': ADAPTER_REVISION,
                'qualification_ref': 'approved-reference-reader',
            }],
        ), resolver=fixture.resolver)

        self.assertIsInstance(disabled, DisabledProviderReferenceReader)
        self.assertTrue(enabled.supports(fixture.stage, 'principal-1'))
        self.assertFalse(enabled.supports(fixture.stage, 'someone-else'))
