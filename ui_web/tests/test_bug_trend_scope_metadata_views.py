import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendAuditEvent, BugTrendCalculationRun, BugTrendScopeProviderBinding, JiraScopeConfig
from jira_sync.app.api.scope_metadata import ScopeConfigOptions, TrackerFieldOption, TrackerOption
from jira_history.models import JiraIssue


from ui_web.tests.bug_trend_scope_config_test_support import (
    FakePartialScopeMetadataFacade,
    FakeScopeMetadataFacade,
    FakeSuccessfulScopeMetadataFacade,
)
from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport


class TestBugTrendScopeMetadataViews(BugTrendScopeConfigViewTestSupport, TestCase):
    def test_shouldRefreshMetadataWithoutSavingScopeConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata refresh',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        original_hash = scope.config_version_hash

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'id': str(scope.id),
                'name': scope.name,
                'jql': 'project = STDEL AND issuetype = Bug AND component = Emulation',
                'bug_type_values': 'Bug',
            })
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertIn('Metadata refresh failed:', content)

    def test_shouldPassCommaSeparatedSelectedProjectsToMetadataRefresh(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata selected projects',
            jql='filter = 131600',
            bug_type_values=['Bug'],
        )
        facade = FakeScopeMetadataFacade()

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = facade
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'selected_projects': '131600, STDEL',
            })

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual([['131600', 'STDEL']], facade.selected_projects)

    def test_shouldPassRepeatedSelectedProjectValuesToMetadataRefresh(self):
        # Given
        facade = FakeScopeMetadataFacade()

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = facade
            response = self.client.get(
                reverse('ui_web:bug_trend_scope_metadata'),
                [('jql', 'filter = 131600'), ('bug_type_values', 'Bug'), ('selected_project', '131600'), ('selected_project', 'STDEL')],
            )

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual([['131600', 'STDEL']], facade.selected_projects)

    def test_shouldHideDiscoveredMetadataCatalogWhileKeepingPickerOptionsInMetadataPartial(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata fields',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeSuccessfulScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertNotIn('Discovered metadata', content)
        self.assertNotIn('scope-metadata-grid', content)
        self.assertNotIn('Add as bug type', content)
        self.assertNotIn('Use as severity field', content)
        self.assertIn('data-searchable-value-picker-value="STDEL"', content)
        self.assertIn('data-searchable-value-picker-value="Bug"', content)
        self.assertIn('data-searchable-value-picker-value="customfield_12345"', content)

    def test_shouldRenderQueryBuilderControlsForHtmxRefresh(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL query builder metadata controls',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeSuccessfulScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'query_builder_issue_types': 'Bug',
                'query_builder_components': 'Emulation',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('id="query-builder-controls"', content)
        self.assertIn('hx-swap-oob="innerHTML"', content)
        self.assertIn('name="query_builder_issue_types"', content)
        self.assertIn('Bug</textarea>', content)
        self.assertIn('name="query_builder_components"', content)
        self.assertIn('Emulation</textarea>', content)

    def test_shouldRenderQueryBuilderMetadataValidationWithoutSavingScopeConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL query builder validation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            source_mode=JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER,
            query_builder_state={'project': 'STDEL', 'issue_types': ['Bug']},
        )
        original_hash = scope.config_version_hash

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeSuccessfulScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'query_builder_issue_types': 'Bug\nManual Type',
                'query_builder_components': 'Emulation',
                'query_builder_labels': 'manual-label',
                'validate_scope': '1',
            })
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertIn('Some values were not found in refreshed Jira metadata.', content)
        self.assertIn('Confirmed: Bug', content)
        self.assertIn('Unconfirmed: Manual Type', content)
        self.assertIn('Manual-only: manual-label', content)

    def test_shouldReopenRequestedPickerAfterMetadataRefresh(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL query builder picker refresh',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeSuccessfulScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'open_picker': 'issue_types',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('id="query-builder-issue-types-menu"', content)
        self.assertIn('searchable-value-picker is-open', content)
        self.assertIn('data-searchable-value-picker-value="Bug"', content)

    def test_shouldRenderMetadataWarningsWithoutDiscoveredCatalog(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL partial metadata',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakePartialScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Unable to load component metadata', content)
        self.assertNotIn('Discovered metadata', content)
        self.assertNotIn('Project: STDEL', content)
        self.assertNotIn('Field: Severity (customfield_12345)', content)
        self.assertIn('data-searchable-value-picker-value="STDEL"', content)
        self.assertIn('data-searchable-value-picker-value="customfield_12345"', content)
