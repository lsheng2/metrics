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


from bug_metrics.app.api import bug_trend_api
from ui_web.facades.bug_trend_facade import BugTrendFacade
from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport, FakeSuccessfulScopeMetadataApi


class TestBugTrendScopeConfigViews(BugTrendScopeConfigViewTestSupport, TestCase):
    def test_shouldRenderScopeLibraryWithCreateEditDuplicateAndDisableActions(self):
        # Given
        enabled_scope = JiraScopeConfig.objects.create(
            name='STDEL enabled library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )
        JiraScopeConfig.objects.create(
            name='STDEL draft library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=False,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('New Scope', content)
        self.assertIn('Import Scope File', content)
        self.assertIn('scope-import-menu', content)
        self.assertIn('STDEL enabled library', content)
        self.assertIn('STDEL draft library', content)
        self.assertIn('scopes', content)
        self.assertNotIn('title="NVU TTL HSD-ES">NVU TTL HSD-ES', content)
        self.assertNotIn('provider_owned_saved_query', content)
        self.assertNotIn('Provider Profile', content)
        self.assertNotIn('href="/ai-dashboard/workflow/?profile_id=nvu-ttl-hsdes"', content)
        self.assertNotIn('href="/data-health/">Health', content)
        self.assertIn(f'?scope_id={enabled_scope.id}', content)
        self.assertIn(f'?duplicate_scope_id={enabled_scope.id}', content)
        self.assertIn('Archive', content)
        self.assertIn('data-confirm="Archive this scope?', content)
        self.assertIn('Dashboard, Workbench, and AI Assistant scope selection', content)
        self.assertIn('Binding', content)
        self.assertIn('title="configuration_required">unbound</span>', content)
        self.assertNotIn('>configuration_required</span>', content)
        self.assertIn('Select a registered provider profile, archive this scope, or delete the archived scope.', content)
        self.assertIn('scope-library-summary', content)
        self.assertIn('Policy', content)
        self.assertIn('compatibility_allowed', content)
        self.assertNotIn('Confirm Inferred Bindings', content)
        self.assertIn('Provider Setup', content)
        self.assertIn('scope-library-table', content)
        self.assertIn('More', content)
        self.assertIn('Binding Audit History', content)
        self.assertIn('No scope binding audit events yet.', content)
        self.assertIn('Scope lifecycle', content)
        self.assertIn('Readiness matrix', content)
        self.assertIn('Deploy to Dashboard selector', content)
        self.assertIn('AI Assistant Grafana charts', content)
        self.assertIn('class="help-tip"', content)
        self.assertIn('Archived scopes are removed from normal selectors', content)
        self.assertIn('compatibility_allowed keeps inferred legacy bindings usable', content)
        self.assertIn('The provider profile selected for this row', content)

    def test_shouldNotAppendUnboundProviderProfilesToScopeLibraryRows(self):
        # Given
        JiraScopeConfig.objects.create(
            name='Only visible scope row',
            jql='project = ONLYSCOPE',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Only visible scope row', content)
        self.assertIn('nvu-ttl-hsdes (hsdes)', content)
        self.assertNotIn('data-label="Name" title="NVU TTL HSD-ES">NVU TTL HSD-ES</td>', content)
        self.assertNotIn('data-label="Source">\n                            <span class="tag is-info">Provider profile</span>', content)

    def test_shouldRenderUnboundScopeWithoutMisleadingProviderValue(self):
        # Given
        JiraScopeConfig.objects.create(
            name='Legacy Jira provider hint only',
            jql='project = LEGACY',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('title="configuration_required">unbound</span>', content)
        self.assertNotIn('data-label="Provider">jira</td>', content)
        self.assertIn('data-label="Provider">-</td>', content)

    def test_shouldKeepScopeLibraryRowActionsCompactInBrowser(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL compact actions',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='STDEL compact actions',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            provenance={'source': 'test', 'matched_by': 'provider_profile_registry'},
        )
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # When
        result = self._measure_scope_library_row_actions(response.content.decode())

        # Then
        self.assertTrue(result['same_row'])
        self.assertEqual([31], result['primary_heights'])
        self.assertTrue(all(width >= 44 for width in result['primary_widths']))
        self.assertLessEqual(max(result['primary_widths']) - min(result['primary_widths']), 2)
        self.assertTrue(result['archive_action_visible'])
        self.assertTrue(result['open_after_summary_click'])
        self.assertFalse(result['open_after_blank_click'])
        self.assertFalse(result['open_after_escape'])
        self.assertFalse(result['horizontal_overflow'])
        self.assertTrue(result['help_tip_visible_on_hover'])
        self.assertLessEqual(result['help_tip_width'], 1)
        self.assertGreaterEqual(result['icon_help_tip_width'], 12)
        self.assertFalse(result['import_file_visible_initial'])
        self.assertTrue(result['import_file_visible_after_open'])

    def test_shouldPromptForArchivedScopeDeleteConfirmationInBrowser(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL archived prompt delete',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=False,
        )
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # When
        result = self._measure_scope_library_delete_confirmation(
            response.content.decode(),
            f'DELETE {scope.name}',
        )

        # Then
        self.assertEqual(200, response.status_code)
        self.assertTrue(result['submitted'])
        self.assertEqual(f'DELETE {scope.name}', result['posted_confirmation'])
        self.assertIn('Type the exact text below into the input box', result['prompt_message'])
        self.assertIn(f'\n\nDELETE {scope.name}\n\n', result['prompt_message'])

    def test_shouldRenderScopeEditorHashWithSharedSignatureSpacingInBrowser(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL signature spacing',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'scope_id': str(scope.id)})

        # When
        result = self._measure_scope_editor_signature_spacing(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, result['signature_item_count'], result)
        self.assertFalse(result['signature_horizontal_overflow'], result)
        self.assertTrue(result['signature_values_fit'], result)
        self.assertGreaterEqual(result['actions_to_signature_gap'], 12, result)

    def test_shouldAdaptScopeLibraryTableAcrossScreenWidthsInBrowser(self):
        # Given
        JiraScopeConfig.objects.create(
            name='Real Intel Jira 131600 Bug Trend Fixture',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            enabled=True,
        )
        explicit_scope = JiraScopeConfig.objects.create(
            name='Real Intel Jira explicit binding fixture',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=explicit_scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            provenance={'source': 'test', 'matched_by': 'provider_profile_registry'},
        )
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # When
        results = self._measure_scope_library_responsive_table(response.content.decode())

        # Then
        self.assertFalse(results['wide']['page_horizontal_overflow'])
        self.assertTrue(results['wide']['table_horizontal_overflow'])
        self.assertNotEqual('none', results['wide']['hash_column_display'])
        self.assertFalse(results['desktop']['page_horizontal_overflow'])
        self.assertTrue(results['desktop']['table_horizontal_overflow'])
        self.assertLessEqual(results['desktop']['scope_lifecycle_height'], 58)
        self.assertLessEqual(results['desktop']['max_body_row_height'], 40)
        self.assertFalse(results['desktop']['actions_wrap'])
        self.assertLessEqual(results['desktop']['primary_action_left_offset_delta'], 2)
        self.assertNotEqual('none', results['desktop']['hash_column_display'])
        self.assertNotEqual('none', results['desktop']['ip_column_display'])
        self.assertNotEqual('none', results['desktop']['project_column_display'])
        self.assertFalse(results['medium']['page_horizontal_overflow'])
        self.assertTrue(results['medium']['table_horizontal_overflow'])
        self.assertNotEqual('none', results['medium']['hash_column_display'])
        self.assertNotEqual('none', results['medium']['ip_column_display'])
        self.assertNotEqual('none', results['medium']['project_column_display'])
        self.assertNotEqual('none', results['medium']['thead_display'])
        self.assertNotEqual('grid', results['medium']['first_cell_display'])
        self.assertFalse(results['phone']['page_horizontal_overflow'])
        self.assertEqual('none', results['phone']['thead_display'])
        self.assertEqual('grid', results['phone']['first_cell_display'])

    def test_shouldConfirmCompatibilityScopeBindingFromLibrary(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL confirm binding',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'source': 'test', 'matched_by': 'legacy_jira_scope'},
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {
            'action': 'confirm_binding',
            'scope_id': str(scope.id),
        })

        # Then
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(302, response.status_code)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertEqual('scope_provider_binding_resolver', binding.provenance['persisted_by'])

    def test_shouldRenderLegacyFallbackScopeAsConfigurationRequiredWithoutFakeProfile(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Legacy visible Jira scope',
            jql='project = LEGACY',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Legacy visible Jira scope', content)
        self.assertIn('title="configuration_required">unbound</span>', content)
        self.assertNotIn('>configuration_required</span>', content)
        self.assertIn('data-label="Profile" title="">-', content)
        self.assertIn('data-label="Provider">-</td>', content)
        self.assertIn('Select a registered provider profile, archive this scope, or delete the archived scope.', content)
        self.assertNotIn('Confirm this inferred provider binding as explicit?', content)

    def test_shouldBulkConfirmCompatibilityScopeBindingsFromLibrary(self):
        # Given
        eligible = JiraScopeConfig.objects.create(
            name='Bulk eligible library',
            jql='project = BULKELIGIBLE',
            bug_type_values=['Bug'],
            enabled=True,
        )
        JiraScopeConfig.objects.create(
            name='Bulk unsafe library',
            jql='',
            bug_type_values=['Bug'],
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=eligible,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'source': 'test', 'matched_by': 'legacy_jira_scope'},
        )

        # When
        response = self.client.post(
            reverse('ui_web:bug_trend_scope_library'),
            {'action': 'bulk_confirm_bindings'},
            follow=True,
        )

        # Then
        content = response.content.decode()
        binding = BugTrendScopeProviderBinding.objects.get(scope=eligible)
        self.assertEqual(200, response.status_code)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertIn('Binding bulk confirmation finished: 1 changed, 1 skipped.', content)
        self.assertIn(BugTrendAuditEvent.EVENT_SCOPE_BINDING_BULK_CONFIRMED, content)

    def test_shouldSaveSelectedProviderProfileBindingFromLibrary(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Unbound library scope',
            jql='',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {
            'action': 'save_binding',
            'scope_id': str(scope.id),
            'profile_id': 'chiplet-2a-jira',
        })

        # Then
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(302, response.status_code)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)

    def test_shouldShowConfigurationRequiredScopeBindingWithoutConfirmAction(self):
        # Given
        JiraScopeConfig.objects.create(
            name='Unbound draft scope',
            jql='',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('title="configuration_required">unbound</span>', content)
        self.assertNotIn('>configuration_required</span>', content)
        self.assertIn('Scope is not bound to a provider profile.', content)
        self.assertNotIn('Confirm binding', content)
        self.assertIn('name="profile_id"', content)
        self.assertIn('chiplet-2a-jira (jira)', content)

    def test_shouldNotShowInlineProviderBindingEditorForArchivedScope(self):
        # Given
        JiraScopeConfig.objects.create(
            name='Archived no inline binding',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=False,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Archived no inline binding', content)
        self.assertIn('Archived: edit, validate, then Enable Scope before provider binding or AI/Grafana use.', content)
        self.assertNotIn('Provider profile for Archived no inline binding', content)

    def test_shouldRenderScopeConfigTerminologyHelp(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Scope config', content)
        self.assertIn('class="help-tip"', content)
        self.assertIn('Jira Query Language used for sync and metadata discovery', content)
        self.assertIn('The time bucket size for trend calculations', content)
        self.assertNotIn('Save</button>', content)

    def test_shouldRenderMutuallyExclusiveSourceModeSections(self):
        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = BugTrendFacade(bug_trend_api, FakeSuccessfulScopeMetadataApi())
            response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                'mode': 'new',
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'query_builder_issue_types': 'Story',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Source population', content)
        self.assertIn('Custom JQL', content)
        self.assertIn('Query Builder', content)
        self.assertIn('This source mode is the single authority for Jira ticket membership.', content)
        self.assertIn('project = STDEL AND issuetype = Story', content)
        self.assertIn('inactive source mode is ignored', content)

    def test_shouldRenderMetadataBackedQueryBuilderControlsWhenMetadataIsLoaded(self):
        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = BugTrendFacade(bug_trend_api, FakeSuccessfulScopeMetadataApi())
            response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                'mode': 'new',
                'refresh_metadata': '1',
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'query_builder_issue_types': 'Bug',
                'query_builder_components': 'Emulation',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('name="query_builder_issue_types" value="Bug" checked', content)
        self.assertIn('name="query_builder_components" value="Emulation" checked', content)
        self.assertIn('name="query_builder_issue_types_manual"', content)
        self.assertIn('name="query_builder_components_manual"', content)
        self.assertIn('Severity (customfield_12345)', content)
        self.assertIn('project = STDEL AND issuetype = Bug AND components = Emulation', content)

    def test_shouldAutoLoadMetadataBackedQueryBuilderControlsForSavedBuilderScope(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL saved builder metadata',
            jql='project = STDEL AND issuetype = Bug AND components = Emulation',
            bug_type_values=['Bug'],
            source_mode=JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER,
            query_builder_state={
                'project': 'STDEL',
                'issue_types': ['Bug'],
                'components': ['Emulation'],
            },
        )

        # When
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = BugTrendFacade(bug_trend_api, FakeSuccessfulScopeMetadataApi())
            response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                'scope_id': str(scope.id),
                'provider_id': 'jira',
            })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('name="query_builder_issue_types" value="Bug" checked', content)
        self.assertIn('name="query_builder_components" value="Emulation" checked', content)
        self.assertNotIn('Refresh metadata to choose issue types values', content)

    def test_shouldRenderQueryBuilderRefreshMetadataButtonNearSourceControls(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'source_mode': 'query_builder',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('scope-query-builder-toolbar', content)
        self.assertIn('Refresh metadata for Query Builder', content)
        self.assertIn('hx-target="#scope-metadata-options"', content)

    def test_shouldUpdateQueryBuilderPreviewFromMetadataControlsInBrowser(self):
        # Given
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = BugTrendFacade(bug_trend_api, FakeSuccessfulScopeMetadataApi())
            response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                'mode': 'new',
                'refresh_metadata': '1',
                'source_mode': 'query_builder',
                'query_builder_project': 'STDEL',
                'query_builder_issue_types': 'Bug',
                'query_builder_components': 'Emulation',
            })

        # When
        results = self._measure_scope_query_builder_metadata_controls(response.content.decode())

        # Then
        for viewport in results.values():
            self.assertFalse(viewport['page_horizontal_overflow'])
            self.assertTrue(viewport['issue_type_checked'])
            self.assertTrue(viewport['component_checked'])
            self.assertGreaterEqual(viewport['metadata_option_count'], 6)
            self.assertGreaterEqual(viewport['custom_field_option_count'], 2)
            self.assertIn('priority = P1-Critical', viewport['preview_value'])
            self.assertIn('resolution = Fixed', viewport['preview_value'])

    def test_shouldSaveQueryBuilderScopeThroughScopeConfigView(self):
        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), {
            'id': '',
            'name': 'STDEL saved from builder',
            'ip': 'NVU',
            'project_label': 'STDEL',
            'source_mode': 'query_builder',
            'jql': 'project = SHOULDNOTSAVE',
            'query_builder_project': 'STDEL',
            'query_builder_issue_types': 'Story',
            'query_builder_components': 'team_int_prc',
            'bug_type_values': 'Story',
            'open_status_values': '',
            'fixed_status_values': '',
            'closed_status_values': '',
            'terminal_excluded_status_values': '',
            'fixed_resolution_values': '',
            'closed_resolution_values': '',
            'reopen_status_values': '',
            'severity_field': '',
            'critical_high_values': '',
            'medium_low_values': '',
            'component_field': '',
            'owner_field': 'assignee',
            'team_field': '',
            'milestone_field': '',
            'fix_version_field': '',
            'package_version_field': '',
            'display_fields': 'customfield_31601',
            'timezone': 'UTC',
            'bucket_granularity': 'weekly',
            'action': 'save_draft',
        })

        # Then
        scope = JiraScopeConfig.objects.get(name='STDEL saved from builder')
        self.assertEqual(302, response.status_code)
        self.assertEqual(JiraScopeConfig.SOURCE_MODE_QUERY_BUILDER, scope.source_mode)
        self.assertEqual('project = STDEL AND issuetype = Story AND components = team_int_prc', scope.jql)
        self.assertEqual({'project': 'STDEL', 'issue_types': ['Story'], 'components': ['team_int_prc']}, scope.query_builder_state)
