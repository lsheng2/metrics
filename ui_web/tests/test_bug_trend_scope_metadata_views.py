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

    def test_shouldRenderDiscoveredFieldOptionsInMetadataPartial(self):
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
        self.assertIn('scope-metadata-grid', content)
        self.assertIn('Projects', content)
        self.assertIn('Types', content)
        self.assertIn('Statuses', content)
        self.assertIn('Fields', content)
        self.assertIn('Maps to Bug type values', content)
        self.assertIn('Project: STDEL', content)
        self.assertIn('Type: Bug', content)
        self.assertIn('Status: Open', content)
        self.assertIn('Priority: P1-Critical', content)
        self.assertIn('Field: Severity (customfield_12345)', content)
        self.assertIn('Add as bug type', content)
        self.assertIn('Use as severity field', content)
        self.assertIn('add_field=bug_type_values', content)
        self.assertIn('add_field=severity_field', content)

    def test_shouldRenderMetadataWarningsAlongsideDiscoveredOptions(self):
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
        self.assertIn('Project: STDEL', content)
        self.assertIn('Field: Severity (customfield_12345)', content)
