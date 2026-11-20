import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendAuditEvent, BugTrendCalculationRun, BugTrendScopeProviderBinding, JiraScopeConfig
from jira_sync.app.api.scope_metadata import ApiForScopeMetadata, ScopeConfigOptions, TrackerFieldOption, TrackerOption
from jira_history.models import JiraIssue


from bug_metrics.app.api import bug_trend_api
from ui_web.facades.bug_trend_facade import BugTrendFacade
from ui_web.tests.bug_trend_scope_config_test_support import (
    FakeEmptyScopeMetadataFacade,
    FakePartialScopeMetadataFacade,
    FakeScopeMetadataFacade,
    FakeSuccessfulScopeMetadataApi,
    FakeSuccessfulScopeMetadataFacade,
)
from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport


class BrowserScopeMetadataProvider:
    def discover_options(self, query: str, selected_projects: list[str], selected_item_types: list[str]):
        if 'ERR' in query or 'ERR' in selected_projects:
            raise RuntimeError('Synthetic metadata unavailable')
        if 'ALT' in query or 'ALT' in selected_projects:
            return ScopeConfigOptions(
                projects=[TrackerOption('ALT', 'ALT')],
                item_types=[TrackerOption('bug-alt', 'Regression Bug')],
                statuses=[TrackerOption('triaged', 'Triaged'), TrackerOption('resolved', 'Resolved')],
                resolutions=[TrackerOption('verified', 'Verified')],
                priorities=[TrackerOption('p0', 'P0-Blocker')],
                fields=[TrackerFieldOption('customfield_alt_severity', 'Synthetic severity', 'Synthetic severity (customfield_alt_severity)')],
                components=[TrackerOption('platform', 'Platform')],
                versions=[TrackerOption('2026.alt', '2026.alt')],
            )
        return ScopeConfigOptions(
            projects=[TrackerOption('STDEL', 'STDEL')],
            item_types=[TrackerOption('bug', 'Bug')],
            statuses=[TrackerOption('open', 'Open'), TrackerOption('fixed', 'Fixed')],
            resolutions=[TrackerOption('done', 'Done')],
            priorities=[TrackerOption('p1', 'P1-Critical')],
            fields=[TrackerFieldOption('priority', 'Priority', 'Priority')],
            components=[TrackerOption('emulation', 'Emulation')],
            versions=[TrackerOption('2026.01', '2026.01')],
        )

    def discover_field_values(self, project_id: str, item_type_ids: list[str], field_id: str):
        return [TrackerOption('browser-value', 'Browser value')]


@override_settings(WHITENOISE_AUTOREFRESH=True)
class TestBugTrendScopeMetadataBrowser(StaticLiveServerTestCase):
    def test_shouldRefreshLoadedMetadataReferenceThroughHtmxWithoutSavingSemanticFields(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL live htmx metadata hint',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            critical_high_values=['P1-Critical'],
            source_mode=JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER,
            query_builder_state={'project': 'STDEL', 'issue_types': ['Bug']},
        )
        original_hash = scope.config_version_hash
        provider = BrowserScopeMetadataProvider()
        facade = BugTrendFacade(
            bug_trend_api,
            ApiForScopeMetadata({'jira': provider}, cache_timeout_seconds=0),
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = facade
            result = self._exercise_htmx_refresh(scope.id)
        scope.refresh_from_db()

        # Then
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertEqual(['Bug'], scope.bug_type_values)
        self.assertEqual(['P1-Critical'], scope.critical_high_values)
        self.assertFalse(result['initial_open'])
        self.assertTrue(result['open_after_refresh'])
        self.assertEqual('Unsaved Browser Bug', result['bug_type_value'])
        self.assertEqual('Unsaved Browser Critical', result['critical_high_value'])
        self.assertIn('P1-Critical', result['before_hint'])
        self.assertIn('Bug', result['before_hint'])
        self.assertIn('P0-Blocker', result['after_hint'])
        self.assertIn('Regression Bug', result['after_hint'])
        self.assertNotIn('P1-Critical', result['after_hint'])

    def test_shouldRenderProviderBoundaryMetadataErrorInBrowser(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL live htmx metadata error',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            source_mode=JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER,
            query_builder_state={'project': 'ERR', 'issue_types': ['Bug']},
        )
        original_hash = scope.config_version_hash
        facade = BugTrendFacade(
            bug_trend_api,
            ApiForScopeMetadata({'jira': BrowserScopeMetadataProvider()}, cache_timeout_seconds=0),
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = facade
            text = self._loaded_hint_text(scope.id, 'ERR')
        scope.refresh_from_db()

        # Then
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertIn('Metadata refresh failed: Synthetic metadata unavailable', text)
        self.assertIn('Metadata refresh could not load the reference.', text)

    def _exercise_htmx_refresh(self, scope_id):
        url = (
            self.live_server_url
            + reverse('ui_web:bug_trend_scope_config')
            + f'?scope_id={scope_id}&refresh_metadata=1&source_mode=query_builder'
            + '&query_builder_project=STDEL&query_builder_issue_types=Bug'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1280, 'height': 900})
                page.goto(url, wait_until='domcontentloaded')
                page.wait_for_selector('.scope-semantic-metadata-reference')
                initial_open = page.locator('.scope-semantic-metadata-reference').evaluate('node => node.open')
                page.locator('.scope-semantic-metadata-reference').evaluate('node => { node.open = true; }')
                before_hint = page.locator('#scope-semantic-metadata-hints-content').inner_text()
                page.fill('#scope-bug-types', 'Unsaved Browser Bug')
                page.fill('#scope-critical-high', 'Unsaved Browser Critical')
                page.fill('#query-builder-project', 'ALT')
                page.locator('#scope-semantic-metadata-hints-content button[hx-get]').click()
                page.wait_for_function(
                    "() => document.querySelector('#scope-semantic-metadata-hints-content')?.innerText.includes('P0-Blocker')",
                )
                return {
                    'initial_open': initial_open,
                    'open_after_refresh': page.locator('.scope-semantic-metadata-reference').evaluate('node => node.open'),
                    'bug_type_value': page.locator('#scope-bug-types').input_value(),
                    'critical_high_value': page.locator('#scope-critical-high').input_value(),
                    'before_hint': before_hint,
                    'after_hint': page.locator('#scope-semantic-metadata-hints-content').inner_text(),
                }
            finally:
                browser.close()

    def _loaded_hint_text(self, scope_id, project):
        url = (
            self.live_server_url
            + reverse('ui_web:bug_trend_scope_config')
            + f'?scope_id={scope_id}&refresh_metadata=1&source_mode=query_builder'
            + f'&query_builder_project={project}&query_builder_issue_types=Bug'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1280, 'height': 900})
                page.goto(url, wait_until='domcontentloaded')
                page.wait_for_selector('#scope-semantic-metadata-hints-content', state='attached')
                return page.locator('#scope-semantic-metadata-hints-content').text_content()
            finally:
                browser.close()


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

    def test_shouldRenderDefaultCollapsedSemanticMappingMetadataReferenceOnFullPage(self):
        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = BugTrendFacade(bug_trend_api, FakeSuccessfulScopeMetadataApi())
            response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                'mode': 'new',
                'refresh_metadata': '1',
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'query_builder_issue_types': 'Bug',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('scope-semantic-metadata-reference', content)
        self.assertIn('id="scope-semantic-metadata-hints-content"', content)
        self.assertEqual(1, content.count('Jira metadata reference'))
        self.assertNotIn('Reference only. Copy values into semantic mapping fields when they match this scope.', content)
        self.assertNotIn('Collapsed by default; refresh does not save the scope.', content)
        self.assertIn('hx-get="/partials/bug-trend/scope-metadata/?refresh_metadata=1"', content)
        self.assertIn('hx-target="#scope-metadata-options"', content)
        self.assertIn('Issue types', content)
        self.assertIn('Bug', content)
        self.assertIn('Priorities', content)
        self.assertIn('P1-Critical', content)
        self.assertNotIn('<details class="disclosure is-flush scope-semantic-metadata-reference" open', content)

    def test_shouldReturnSemanticMappingMetadataHintsOutOfBandWithoutReplacingUserMappings(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL semantic hint metadata controls',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            critical_high_values=['P1-Critical'],
        )
        original_hash = scope.config_version_hash

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeSuccessfulScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'bug_type_values': 'Unsaved Bug',
                'critical_high_values': 'Unsaved Critical',
            })
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertEqual(['Bug'], scope.bug_type_values)
        self.assertIn('id="scope-semantic-metadata-hints-content"', content)
        self.assertIn('hx-swap-oob="innerHTML"', content)
        self.assertNotIn('Jira metadata reference</span>', content)
        self.assertNotIn('Reference only. Copy values into semantic mapping fields when they match this scope.', content)
        self.assertIn('Issue types', content)
        self.assertIn('P1-Critical', content)
        self.assertIn('Severity (customfield_12345)', content)
        self.assertNotIn('name="bug_type_values"', content)
        self.assertNotIn('Unsaved Bug</textarea>', content)

    def test_shouldRenderSemanticMappingMetadataHintWarningAndEmptyStates(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL semantic hint empty states',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeScopeMetadataFacade()
            error_response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakePartialScopeMetadataFacade()
            warning_response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = FakeEmptyScopeMetadataFacade()
            empty_response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})

        # Then
        error_content = error_response.content.decode()
        warning_content = warning_response.content.decode()
        empty_content = empty_response.content.decode()
        self.assertEqual(200, error_response.status_code)
        self.assertEqual(200, warning_response.status_code)
        self.assertEqual(200, empty_response.status_code)
        self.assertIn('Metadata refresh failed: offline', error_content)
        self.assertIn('Metadata refresh could not load the reference.', error_content)
        self.assertIn('Unable to load component metadata', warning_content)
        self.assertIn('Severity (customfield_12345)', warning_content)
        self.assertIn('No discovered metadata values are available for this Jira context.', empty_content)

    def test_shouldRenderNonJiraSemanticMetadataHintWithoutCallingJiraMetadata(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='HSDES semantic hint metadata controls',
            jql='subject = "ttl"',
            bug_type_values=['defect'],
        )
        facade = FakeScopeMetadataFacade()

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = facade
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'provider_id': 'hsdes',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual([], facade.selected_projects)
        self.assertIn('id="scope-semantic-metadata-hints-content"', content)
        self.assertIn('Jira metadata reference is available for Jira scopes only.', content)
        self.assertNotIn('id="query-builder-controls"', content)

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
