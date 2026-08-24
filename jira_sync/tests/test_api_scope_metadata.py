from django.test import TestCase
from django.core.cache import cache

from bug_metrics.models import JiraScopeConfig
from jira_sync.app.api.scope_metadata import ApiForScopeMetadata
from jira_sync.out.jira_scope_metadata_adapter import JiraScopeMetadataAdapter


class FakeJiraMetadataClient:
    def __init__(self):
        self.field_options_requested = []
        self.issue_type_requests = 0

    def issue_createmeta_issuetypes(self, project_key):
        self.issue_type_requests += 1
        return [
            {'id': '1', 'name': 'Bug'},
            {'id': '2', 'name': 'Feature'},
        ]

    def get_status_for_project(self, project_key):
        return [
            {'id': '1', 'name': 'Bug', 'statuses': [{'id': '11', 'name': 'Open'}, {'id': '12', 'name': 'Fixed'}]},
            {'id': '2', 'name': 'Feature', 'statuses': [{'id': '13', 'name': 'Open'}]},
        ]

    def get_all_resolutions(self):
        return [{'id': '10000', 'name': 'Done'}]

    def get_all_priorities(self):
        return [{'id': '1', 'name': 'P1-Critical'}, {'id': '2', 'name': 'P2-High'}]

    def get_all_fields(self):
        return [
            {'id': 'priority', 'name': 'Priority', 'schema': {'type': 'priority'}},
            {'id': 'customfield_12345', 'name': 'Severity', 'schema': {'type': 'option'}},
        ]

    def get_project_components(self, project_key):
        return [{'id': '20000', 'name': 'Emulation'}]

    def get_project_versions(self, project_key):
        return [{'id': '30000', 'name': '2026.01'}]

    def get_project(self, project_key):
        return {'id': '131600', 'key': project_key}

    def get_custom_field_options(self, field_id, project_id, issue_type_id=None, query=None, page=None, limit=None, sort=None, use_all_contexts=None):
        self.field_options_requested.append((field_id, project_id, issue_type_id))
        return [{'id': '40000', 'value': 'Critical'}, {'id': '40001', 'value': 'Medium'}]


class TestScopeMetadataApi(TestCase):
    def setUp(self):
        cache.clear()

    def test_shouldDiscoverProjectScopedJiraOptionsWithoutSavingScopeConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL scope metadata',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})
        original_hash = scope.config_version_hash

        # When
        options = api.discover_scope_options('jira', scope.jql, [], ['Bug'])
        scope.refresh_from_db()

        # Then
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertEqual(['STDEL'], [project.id for project in options.projects])
        self.assertEqual(['Bug', 'Feature'], [item_type.name for item_type in options.item_types])
        self.assertEqual(['Open', 'Fixed'], [status.name for status in options.statuses])
        self.assertEqual(['Done'], [resolution.name for resolution in options.resolutions])
        self.assertEqual(['P1-Critical', 'P2-High'], [priority.name for priority in options.priorities])
        self.assertEqual(['priority', 'customfield_12345'], [field.id for field in options.fields])
        self.assertEqual(['Emulation'], [component.name for component in options.components])
        self.assertEqual(['2026.01'], [version.name for version in options.versions])

    def test_shouldUseSelectedProjectsWhenQueryCannotBeParsed(self):
        # Given
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})

        # When
        options = api.discover_scope_options('jira', 'filter = 131600', ['STDEL'], ['Bug'])

        # Then
        self.assertEqual(['STDEL'], [project.id for project in options.projects])
        self.assertEqual(['Open', 'Fixed'], [status.name for status in options.statuses])

    def test_shouldDiscoverNumericProjectIdFromScopeQuery(self):
        # Given
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})

        # When
        options = api.discover_scope_options('jira', 'project = 131600 AND issuetype = Bug', [], ['Bug'])

        # Then
        self.assertEqual(['131600'], [project.id for project in options.projects])
        self.assertEqual(['Open', 'Fixed'], [status.name for status in options.statuses])

    def test_shouldDiscoverQuotedProjectKeyFromScopeQuery(self):
        # Given
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})

        # When
        options = api.discover_scope_options('jira', 'project = "STDEL" AND issuetype = Bug', [], ['Bug'])

        # Then
        self.assertEqual(['STDEL'], [project.id for project in options.projects])
        self.assertEqual(['Open', 'Fixed'], [status.name for status in options.statuses])

    def test_shouldDiscoverMixedProjectTokensFromScopeQuery(self):
        # Given
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})

        # When
        options = api.discover_scope_options('jira', 'project in (131600, "STDEL") AND issuetype = Bug', [], ['Bug'])

        # Then
        self.assertEqual(['131600', 'STDEL'], [project.id for project in options.projects])

    def test_shouldWarnWhenNoProjectCanBeResolvedForProjectScopedMetadata(self):
        # Given
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})

        # When
        options = api.discover_scope_options('jira', 'filter = 131600', [], ['Bug'])

        # Then
        self.assertEqual([], options.projects)
        self.assertIn('Select at least one Jira project before refreshing project-scoped metadata.', options.warnings)

    def test_shouldDiscoverFieldValuesThroughProviderAdapter(self):
        # Given
        client = FakeJiraMetadataClient()
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(client)})

        # When
        values = api.discover_field_values('jira', 'STDEL', ['Bug'], 'customfield_12345')

        # Then
        self.assertEqual([('12345', '131600', None)], client.field_options_requested)
        self.assertEqual(['Critical', 'Medium'], [value.name for value in values])

    def test_shouldPassNumericIssueTypeIdsWhenDiscoveringCustomFieldValues(self):
        # Given
        client = FakeJiraMetadataClient()
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(client)})

        # When
        api.discover_field_values('jira', 'STDEL', ['1'], 'customfield_12345')

        # Then
        self.assertEqual([('12345', '131600', ['1'])], client.field_options_requested)

    def test_shouldMatchInstalledJiraCustomFieldOptionsSignature(self):
        # Given / When
        import inspect
        from atlassian import Jira

        signature = inspect.signature(Jira.get_custom_field_options)

        # Then
        self.assertIn('field_id', signature.parameters)
        self.assertIn('project_id', signature.parameters)
        self.assertIn('issue_type_id', signature.parameters)

    def test_shouldRejectUnsupportedProvider(self):
        # Given
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(FakeJiraMetadataClient())})

        # When / Then
        with self.assertRaises(ValueError):
            api.discover_scope_options('github', 'repo:owner/name', [], [])

    def test_shouldCacheScopeOptionsUntilRefreshBypass(self):
        # Given
        client = FakeJiraMetadataClient()
        api = ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(client)}, cache_timeout_seconds=300)

        # When
        api.discover_scope_options('jira', 'project = STDEL', [], ['Bug'])
        api.discover_scope_options('jira', 'project = STDEL', [], ['Bug'])
        api.discover_scope_options('jira', 'project = STDEL', [], ['Bug'], refresh=True)

        # Then
        self.assertEqual(2, client.issue_type_requests)