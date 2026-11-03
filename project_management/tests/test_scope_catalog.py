import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from bug_metrics.app.api import ApiForBugTrend
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig
from project_management.app.api import ApiForProjectManagement
from project_management.app.domain.contracts import ProjectActor, ProjectError, ScopeSelection
from project_management.out.dashboard_scope_catalog import DashboardScopeCatalog


class TestDashboardScopeCatalog(TestCase):
    def setUp(self):
        self.scope = JiraScopeConfig.objects.create(name='Example Scope', jql='project = ALPHA', enabled=True)
        self.binding = BugTrendScopeProviderBinding.objects.create(
            scope=self.scope, profile_id='alpha-jira', provider_id='jira', status='explicit',
        )
        self.records = [
            self.profile('alpha-jira', 'jira'),
            self.profile('beta-hsd', 'hsdes', source_query_ref='query-2', source_query_hash='hash-2'),
            self.profile('gamma-hsd', 'hsdes', source_query_ref='query-3', source_query_hash='hash-3'),
        ]
        self.registry = lambda: ProjectProviderProfileRegistry.from_records(self.records)
        registry_patch = patch.object(ProjectProviderProfileRegistry, 'load_default', side_effect=self.registry)
        registry_patch.start()
        self.addCleanup(registry_patch.stop)
        self.catalog = DashboardScopeCatalog(ApiForBugTrend(), self.registry)

    def profile(self, profile_id, provider_id, **source):
        return {
            'profile_id': profile_id, 'provider_id': provider_id, 'enabled': True,
            'connection_settings': {
                'base_url': 'https://tracker.example.test', 'api_token': 'never-output-this-secret',
            },
            'source_population': source,
        }

    def assert_error(self, code, selection):
        with self.assertRaises(ProjectError) as raised:
            self.catalog.resolve(selection)
        self.assertEqual(code, raised.exception.code)

    def test_shouldFreezeExactJiraQueryWithoutCredentials(self):
        descriptor = self.catalog.resolve(ScopeSelection('alpha-jira', self.scope.id))
        self.assertEqual('project = ALPHA', descriptor.query)
        self.assertEqual('jql', descriptor.query_kind)
        self.assertNotIn('never-output-this-secret', repr(descriptor))

    def test_shouldRejectInferredOrWrongProviderBindings(self):
        self.binding.status = 'compatibility'
        self.binding.save()
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('alpha-jira', self.scope.id))
        self.binding.status = 'explicit'
        self.binding.provider_id = 'hsdes'
        self.binding.save()
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('alpha-jira', self.scope.id))

    def test_shouldRejectUnboundAndDisabledScopes(self):
        self.binding.delete()
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('alpha-jira', self.scope.id))
        self.scope.enabled = False
        self.scope.save()
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('alpha-jira', self.scope.id))

    def test_shouldNotChangeRuleForMetricMappingsOrDisplayNames(self):
        first = self.catalog.resolve(ScopeSelection('alpha-jira', self.scope.id))
        self.scope.name = 'Renamed'
        self.scope.critical_high_values = ['Urgent']
        self.scope.save()
        self.assertEqual(first, self.catalog.resolve(ScopeSelection('alpha-jira', self.scope.id)))
        self.scope.jql = 'project = BETA'
        self.scope.save()
        self.assertNotEqual(first.definition_hash(), self.catalog.resolve(
            ScopeSelection('alpha-jira', self.scope.id),
        ).definition_hash())

    def test_shouldUseSeparateHsdesSavedQueryScopesWithoutJira(self):
        beta = self.catalog.resolve(ScopeSelection('beta-hsd'))
        gamma = self.catalog.resolve(ScopeSelection('gamma-hsd'))
        self.assertEqual(('hsdes', 'saved_query', 'query-2'), (beta.provider_id, beta.query_kind, beta.source_ref))
        self.assertEqual('query-2', json.loads(beta.query)['source_query_ref'])
        self.assertNotEqual(beta.definition_hash(), gamma.definition_hash())
        self.assert_error('INVALID_SELECTION', ScopeSelection('beta-hsd', self.scope.id))
        self.assert_error('INVALID_SELECTION', ScopeSelection('alpha-jira'))

    def test_shouldRejectMissingHsdesVersionOrReference(self):
        self.records[1]['source_population'] = {}
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('beta-hsd'))

    def test_shouldDetectEndpointChangesAndRejectSecretBearingUrls(self):
        selection = ScopeSelection('alpha-jira', self.scope.id)
        first = self.catalog.resolve(selection)
        self.records[0]['connection_settings']['base_url'] = 'https://other.example.test'
        self.assertNotEqual(first.definition_hash(), self.catalog.resolve(selection).definition_hash())
        for endpoint in ['https://user:secret@example.test', 'https://example.test?token=x', 'file:///tmp']:
            self.records[0]['connection_settings']['base_url'] = endpoint
            self.assert_error('SOURCE_UNAVAILABLE', selection)

    @override_settings(METRICS_JIRA_SERVER_URL='https://configured.example.test')
    def test_shouldResolveOnlyTheDeclaredLocalEndpointSetting(self):
        self.records[0]['connection_settings']['base_url'] = 'settings:METRICS_JIRA_SERVER_URL'
        descriptor = self.catalog.resolve(ScopeSelection('alpha-jira', self.scope.id))
        self.assertEqual('https://configured.example.test', descriptor.endpoint)
        self.records[0]['connection_settings']['base_url'] = 'settings:SECRET_KEY'
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('alpha-jira', self.scope.id))

    def test_shouldKeepStageAfterDeletingExternalScope(self):
        api = ApiForProjectManagement(self.catalog)
        actor = ProjectActor('operator')
        project = api.create_project(actor, key='alpha', name='Alpha')
        stage = api.add_stage(actor, project.id, key='release', name='Release',
                              selection=ScopeSelection('alpha-jira', self.scope.id))
        self.scope.delete()
        detail = api.get_project(actor, project.id)
        self.assertEqual(stage.id, detail.stages[0].id)
        self.assertEqual('unavailable', detail.stages[0].source_status)

    def test_shouldRejectUnavailableProfilesAndUnsupportedProviders(self):
        self.records[0]['enabled'] = False
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('alpha-jira', self.scope.id))
        self.records.append(self.profile('other-provider', 'github'))
        self.assert_error('INVALID_SELECTION', ScopeSelection('other-provider'))
        self.assert_error('SOURCE_UNAVAILABLE', ScopeSelection('missing'))

    def test_shouldReadScopeThroughProductionPublicApiWithoutNetwork(self):
        with patch.object(ProjectProviderProfileRegistry, 'load_default', side_effect=self.registry):
            descriptor = DashboardScopeCatalog().resolve(ScopeSelection('alpha-jira', self.scope.id))
        self.assertEqual(f'scope:{self.scope.id}', descriptor.source_ref)
