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


class FakeScopeMetadataFacade:
    def __init__(self):
        self.selected_projects = []

    def get_scope_config(self, scope_id):
        from bug_metrics.app.api import bug_trend_api
        return bug_trend_api.get_scope_config(scope_id)

    def scope_config_from_post(self, post_data):
        from ui_web.facades.bug_trend_facade import BugTrendFacade
        from bug_metrics.app.api import bug_trend_api
        return BugTrendFacade(bug_trend_api).scope_config_from_post(post_data)

    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return {'warnings': ['Metadata refresh failed: offline'], 'options': None}


class FakeSuccessfulScopeMetadataFacade(FakeScopeMetadataFacade):
    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return ScopeConfigOptions(
            projects=[TrackerOption('STDEL', 'STDEL')],
            item_types=[TrackerOption('1', 'Bug')],
            statuses=[TrackerOption('11', 'Open')],
            resolutions=[TrackerOption('21', 'Fixed')],
            priorities=[TrackerOption('31', 'P1-Critical')],
            fields=[TrackerFieldOption('customfield_12345', 'Severity', 'Severity (customfield_12345)')],
            components=[TrackerOption('41', 'Emulation')],
            versions=[TrackerOption('51', '2026.01')],
        )


class FakePartialScopeMetadataFacade(FakeScopeMetadataFacade):
    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return {
            'warnings': ['Unable to load component metadata'],
            'options': ScopeConfigOptions(
                projects=[TrackerOption('STDEL', 'STDEL')],
                fields=[TrackerFieldOption('customfield_12345', 'Severity', 'Severity (customfield_12345)')],
            ),
        }


class TestBugTrendScopeConfigViews(TestCase):
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
        self.assertIn('provider profiles', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('NVU1.0_TTL', content)
        self.assertIn('Provider profile', content)
        self.assertIn('provider_owned_saved_query', content)
        self.assertIn('Workflow', content)
        self.assertIn('Health', content)
        self.assertIn(f'?scope_id={enabled_scope.id}', content)
        self.assertIn(f'?duplicate_scope_id={enabled_scope.id}', content)
        self.assertIn('Archive', content)
        self.assertIn('data-confirm="Archive this scope?', content)
        self.assertIn('Dashboard, Workbench, and AI Assistant scope selection', content)
        self.assertIn('Binding', content)
        self.assertIn('compatibility', content)
        self.assertIn('Confirm', content)
        self.assertIn('scope-library-summary', content)
        self.assertIn('Policy', content)
        self.assertIn('compatibility_allowed', content)
        self.assertIn('Confirm Inferred Bindings', content)
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
        self.assertIn(f'DELETE {scope.name}', result['prompt_message'])

    def test_shouldAdaptScopeLibraryTableAcrossScreenWidthsInBrowser(self):
        # Given
        JiraScopeConfig.objects.create(
            name='Real Intel Jira 131600 Bug Trend Fixture',
            jql='project = 131600 AND component = team_int_qemu',
            bug_type_values=['Bug'],
            enabled=True,
        )
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # When
        results = self._measure_scope_library_responsive_table(response.content.decode())

        # Then
        self.assertFalse(results['wide']['page_horizontal_overflow'])
        self.assertFalse(results['wide']['table_horizontal_overflow'])
        self.assertNotEqual('none', results['wide']['hash_column_display'])
        self.assertFalse(results['desktop']['page_horizontal_overflow'])
        self.assertLessEqual(results['desktop']['max_body_row_height'], 42)
        self.assertFalse(results['desktop']['actions_wrap'])
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
            profile_id='STDEL confirm binding',
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
        self.assertEqual('STDEL confirm binding', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertEqual('scope_provider_binding_resolver', binding.provenance['persisted_by'])

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
            profile_id='Bulk eligible library',
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
        self.assertIn('configuration_required', content)
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

    def test_shouldRenderProviderContextAndReadinessOnScopeConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            jql='project = 131600 AND issuetype = Bug',
            bug_type_values=['Bug'],
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            provenance={'source': 'test', 'matched_by': 'operator_confirmed'},
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Choose provider first', content)
        self.assertIn('chiplet-2a-jira (jira)', content)
        self.assertIn('operator_confirmed', content)
        self.assertIn('Save Draft requires', content)
        self.assertIn('Enable Scope requires', content)
        self.assertIn('Provider metadata uses', content)
        self.assertIn('IP and Project label are display/binding hints', content)
        self.assertIn('Save binding', content)
        self.assertIn('scope-provider-choice is-provider-green is-selected', content)
        self.assertIn('scope-provider-choice is-provider-blue', content)
        self.assertIn('scope-config-provider-panel provider-tab-shell is-provider-green', content)
        self.assertIn('provider-tab-check', content)
        self.assertIn('role="tablist"', content)
        self.assertIn('role="tabpanel"', content)

    def test_shouldSaveProviderBindingFromScopeConfigWithoutSavingScopeFields(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Scope config binding target',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), {
            'action': 'save_binding',
            'id': str(scope.id),
            'profile_id': 'chiplet-2a-jira',
            'name': 'Unsaved rename must not persist',
            'jql': 'project = DIFFERENT',
        }, follow=True)
        scope.refresh_from_db()

        # Then
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(200, response.status_code)
        self.assertEqual('Scope config binding target', scope.name)
        self.assertEqual('project = STDEL', scope.jql)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertIn('Provider binding saved.', response.content.decode())

    def test_shouldRenderNewScopeProviderFirstChoices(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Choose provider first', content)
        self.assertIn('scope-provider-choice is-provider-green is-selected', content)
        self.assertIn('Jira</span>', content)
        self.assertIn('scope-provider-choice is-provider-blue', content)
        self.assertIn('HSD-ES</span>', content)
        self.assertIn('provider-tab-check', content)
        self.assertIn('aria-selected="true"', content)
        self.assertIn('name="provider_id" value="jira"', content)
        self.assertIn('Jira metadata refresh is available from JQL project, Selected Jira projects and bug type values.', content)
        self.assertIn('GitHub', content)
        self.assertIn('is-provider-purple', content)

    def test_shouldRenderHsdesProviderTemplateOnNewScope(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'hsdes',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('scope-provider-choice is-provider-blue is-selected', content)
        self.assertIn('scope-config-provider-panel provider-tab-shell is-provider-blue', content)
        self.assertIn('provider-tab-check', content)
        self.assertIn('name="provider_id" value="hsdes"', content)
        self.assertIn('nvu-ttl-hsdes (hsdes)', content)
        self.assertIn('HSD-ES source reference', content)
        self.assertIn('saved query', content)
        self.assertIn('query id', content)
        self.assertIn('Refresh metadata unavailable', content)
        self.assertIn('provider profile workflow/readiness', content)

    def test_shouldKeepScopeConfigProviderTabsUsableAcrossDesktopAndPhoneInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
        })
        results = self._measure_scope_config_provider_tabs(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertFalse(results['desktop']['page_horizontal_overflow'])
        self.assertFalse(results['phone']['page_horizontal_overflow'])
        self.assertGreaterEqual(results['desktop']['tab_count'], 3)
        self.assertTrue(results['desktop']['selected_check_visible'])
        self.assertTrue(results['phone']['selected_check_visible'])
        self.assertTrue(results['desktop']['tab_shell_wraps_provider_content'])
        self.assertTrue(results['phone']['tab_shell_wraps_provider_content'])
        self.assertTrue(results['desktop']['tab_body_visible'])
        self.assertTrue(results['phone']['tab_body_visible'])
        self.assertTrue(results['desktop']['selected_tab_attached_to_body'])
        self.assertTrue(results['desktop']['selected_tab_is_hsdes'])
        self.assertTrue(results['desktop']['shell_border_is_blue'])
        self.assertLessEqual(results['desktop']['detail_panel_left_border_width'], 1)
        self.assertLessEqual(results['desktop']['provider_choice_max_height'], 82)
        self.assertLessEqual(results['desktop']['scope_form_control_height_delta'], 1)
        self.assertLessEqual(results['phone']['scope_form_control_height_delta'], 1)

    def test_shouldSaveNewScopeWithSelectedProviderProfileBinding(self):
        # Given
        payload = {
            'id': '',
            'name': 'Provider first new scope',
            'ip': 'NVU',
            'project_label': 'Chiplet',
            'jql': 'project = "131600"',
            'bug_type_values': 'Bug',
            'open_status_values': 'Open',
            'fixed_status_values': 'Fixed',
            'closed_status_values': '',
            'terminal_excluded_status_values': '',
            'fixed_resolution_values': '',
            'closed_resolution_values': '',
            'reopen_status_values': '',
            'severity_field': 'priority',
            'critical_high_values': 'P1-Critical',
            'medium_low_values': 'P3-Medium',
            'component_field': 'components',
            'owner_field': 'assignee',
            'team_field': '',
            'milestone_field': '',
            'fix_version_field': '',
            'package_version_field': '',
            'display_fields': '',
            'timezone': 'UTC',
            'bucket_granularity': 'weekly',
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'action': 'save_draft',
        }

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload, follow=True)

        # Then
        scope = JiraScopeConfig.objects.get(name='Provider first new scope')
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertFalse(scope.enabled)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertIn('Provider binding saved.', content)

    def test_shouldDisableScopeFromLibraryWithoutDeletingConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL disable from library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {'action': 'disable', 'scope_id': str(scope.id)})
        scope.refresh_from_db()

        # Then
        self.assertEqual(302, response.status_code)
        self.assertFalse(scope.enabled)
        self.assertTrue(JiraScopeConfig.objects.filter(id=scope.id).exists())

    def test_shouldExportScopeConfigPackageFromLibrary(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL export from library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'), {'export_scope_id': str(scope.id)})

        # Then
        package = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('attachment; filename="scope-%s.json"' % scope.id, response['Content-Disposition'])
        self.assertEqual('metrics.scope-config', package['format'])
        self.assertEqual('STDEL export from library', package['scope']['name'])
        self.assertIn('calculation_runs', package['excludes'])

    def test_shouldImportScopePackageAsArchivedScopeFromLibrary(self):
        # Given
        package = {
            'format': 'metrics.scope-config',
            'version': 1,
            'scope': {
                'id': 999,
                'name': 'STDEL imported library',
                'ip': 'NVU',
                'project_label': 'STDEL',
                'jql': 'project = STDEL',
                'bug_type_values': ['Bug'],
                'open_status_values': ['New'],
                'fixed_status_values': ['Fixed'],
                'closed_status_values': [],
                'terminal_excluded_status_values': [],
                'fixed_resolution_values': [],
                'closed_resolution_values': [],
                'reopen_status_values': [],
                'severity_field': 'priority',
                'critical_high_values': ['P1-Critical'],
                'medium_low_values': ['P3-Medium'],
                'component_field': '',
                'owner_field': 'assignee',
                'team_field': '',
                'milestone_field': '',
                'fix_version_field': '',
                'package_version_field': '',
                'display_fields': [],
                'timezone': 'UTC',
                'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
                'enabled': True,
                'config_version_hash': 'source-hash',
            },
            'provider_binding': {
                'profile_id': 'chiplet-2a-jira',
                'provider_id': 'jira',
                'status': 'explicit',
            },
        }
        upload = SimpleUploadedFile('scope.json', json.dumps(package).encode('utf-8'), content_type='application/json')

        # When
        response = self.client.post(
            reverse('ui_web:bug_trend_scope_library'),
            {'action': 'import_scope', 'scope_package': upload},
            follow=True,
        )

        # Then
        imported = JiraScopeConfig.objects.get(name='STDEL imported library imported')
        binding = BugTrendScopeProviderBinding.objects.get(scope=imported)
        self.assertEqual(200, response.status_code)
        self.assertFalse(imported.enabled)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertIn('Imported STDEL imported library imported as an archived draft.', response.content.decode())

    def test_shouldDeleteOnlyArchivedScopeFromLibraryWithConfirmation(self):
        # Given
        enabled_scope = JiraScopeConfig.objects.create(
            name='STDEL enabled protected delete',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )
        archived_scope = JiraScopeConfig.objects.create(
            name='STDEL archived delete from library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            enabled=False,
        )

        # When
        protected_response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {
            'action': 'delete_archived',
            'scope_id': str(enabled_scope.id),
            'delete_confirmation': 'DELETE STDEL enabled protected delete',
        }, follow=True)
        deleted_response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {
            'action': 'delete_archived',
            'scope_id': str(archived_scope.id),
            'delete_confirmation': 'DELETE STDEL archived delete from library',
        }, follow=True)

        # Then
        self.assertTrue(JiraScopeConfig.objects.filter(id=enabled_scope.id).exists())
        self.assertFalse(JiraScopeConfig.objects.filter(id=archived_scope.id).exists())
        self.assertIn('Only archived scopes can be deleted.', protected_response.content.decode())
        self.assertIn('Archived scope deleted', deleted_response.content.decode())

    def test_shouldRenderNewScopeEditorWithoutExistingScopeId(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Save Draft', content)
        self.assertIn('Enable Scope', content)
        self.assertIn('Cancel Editing', content)
        self.assertIn('scope-editor-actions', content)
        self.assertIn('provider-action-cancel', content)
        self.assertIn('data-dirty-form', content)
        self.assertIn('hx-include="closest form"', content)
        self.assertIn('value=""', content)
        self.assertNotIn('Scope Audit', content)

    def test_shouldMarkUnsavedScopeFieldAndShowConsistentEditorActionsInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})
        result = self._measure_scope_config_dirty_state(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, result['initial_dirty_fields'])
        self.assertTrue(result['dirty_field_highlighted'])
        self.assertTrue(result['dirty_control_highlighted'])
        self.assertTrue(result['dirty_banner_visible'])
        self.assertIn('Unsaved *', result['dirty_label_text'])
        self.assertTrue(result['cancel_button_visible'])
        self.assertLessEqual(result['action_button_height_delta'], 1)
        self.assertGreaterEqual(result['action_gap_px'], 8)
        self.assertFalse(result['page_horizontal_overflow'])

    def test_shouldHighlightActionRequiredScopeFieldsInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})
        result = self._measure_scope_required_validation(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(['name', 'jql', 'bug_type_values'], result['save_draft_missing_names'])
        self.assertTrue(result['save_draft_summary_visible'])
        self.assertEqual('scope-name', result['save_draft_focused_id'])
        self.assertIn('At least one bug type value is required before saving this scope.', result['save_draft_messages'])
        self.assertEqual(
            [
                'critical_high_values',
                'medium_low_values',
                'open_status_values',
                'fixed_status_values',
                'closed_status_values',
                'severity_field',
            ],
            result['enable_missing_names'],
        )
        self.assertTrue(result['enable_summary_visible'])
        self.assertEqual('scope-critical-high', result['enable_focused_id'])
        self.assertIn('Add at least one fixed or closed status value before enabling this scope.', result['enable_messages'])

    def test_shouldRenderDuplicateEditorAsDisabledDraftWithoutMutatingSource(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL source duplicate',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'duplicate_scope_id': str(scope.id)})
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('STDEL source duplicate copy', content)
        self.assertIn('Save Draft', content)
        self.assertNotIn('Scope Audit', content)
        self.assertTrue(scope.enabled)

    def test_shouldLinkUnmappedAuditSeverityIntoConfigEditorWithoutSaving(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL config handoff',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            severity_field='priority',
            critical_high_values=['P2-High'],
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-9001',
            issue_type='Bug',
            status='New',
            severity_value='P1-Stopper',
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        # When
        audit_response = self.client.get(reverse('ui_web:bug_trend_scope_audit'), {'scope_id': scope.id})
        config_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'scope_id': scope.id,
            'add_field': 'critical_high_values',
            'add_value': 'P1-Stopper',
        })
        scope.refresh_from_db()

        # Then
        self.assertEqual(200, audit_response.status_code)
        self.assertIn('Add as critical/high', audit_response.content.decode())
        self.assertEqual(200, config_response.status_code)
        self.assertIn('P1-Stopper', config_response.content.decode())
        self.assertEqual(['P2-High'], scope.critical_high_values)

    def test_shouldSaveScopeConfigAndShowRecalculationPromptWhenSemanticHashChanges(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL config save',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P2-High'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )
        original_hash = scope.config_version_hash
        BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=original_hash,
            source_coverage_start=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            source_coverage_end=datetime(2026, 8, 31, tzinfo=timezone.utc).date(),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), self._post_payload(scope, 'P2-High\nP1-Stopper'), follow=True)
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertNotEqual(original_hash, scope.config_version_hash)
        self.assertEqual(['P2-High', 'P1-Stopper'], scope.critical_high_values)
        self.assertIn('Scope config saved.', content)
        self.assertIn('Semantic config changed. Recalculate this scope before using existing Bug Trend runs as current evidence.', content)

    def test_shouldRenderExistingEnabledScopeSaveAsChangesNotDraft(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL enabled edit label',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Save Changes', content)

    def test_shouldRenderValidationErrorsWhenScopeConfigPostIsInvalid(self):
        # Given
        first_scope = JiraScopeConfig.objects.create(
            name='STDEL duplicate owner',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        second_scope = JiraScopeConfig.objects.create(
            name='STDEL editable',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        payload = self._post_payload(second_scope, 'P2-High')
        payload['name'] = first_scope.name

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload)
        second_scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Scope config was not saved.', content)
        self.assertIn('name: Scope name must be unique.', content)
        self.assertEqual('STDEL editable', second_scope.name)

    def test_shouldCreateDraftScopeWhenScopeConfigPostHasNoId(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL editable no id',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        payload = self._post_payload(scope, 'P2-High')
        payload['id'] = ''
        payload['name'] = 'STDEL created from form'
        payload['action'] = 'save_draft'

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload, follow=True)

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        created = JiraScopeConfig.objects.get(name='STDEL created from form')
        self.assertFalse(created.enabled)
        self.assertIn('Scope config saved.', content)

    def test_shouldRenderValidationErrorsWhenScopeConfigPostHasMalformedId(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL editable bad id',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        payload = self._post_payload(scope, 'P2-High')
        payload['id'] = 'abc'

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Scope config was not saved.', content)
        self.assertIn('id: Scope id must be numeric.', content)

    def test_shouldRenderValidationErrorsWhenScopeConfigGetHasMalformedScopeId(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'scope_id': 'abc'})

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Scope config was not saved.', content)
        self.assertIn('scope_id: A valid scope id is required.', content)
        self.assertNotIn('Save scope config', content)

    def test_shouldRefreshMetadataWithoutSavingScopeConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata refresh',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        original_hash = scope.config_version_hash

        # When
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
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
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
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
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
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
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
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
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
            container.bug_trend_facade = FakePartialScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Unable to load component metadata', content)
        self.assertIn('Project: STDEL', content)
        self.assertIn('Field: Severity (customfield_12345)', content)


    def _post_payload(self, scope, critical_high_values):
        return {
            'id': str(scope.id),
            'name': scope.name,
            'ip': scope.ip,
            'project_label': scope.project_label,
            'jql': scope.jql,
            'bug_type_values': '\n'.join(scope.bug_type_values),
            'open_status_values': '\n'.join(scope.open_status_values),
            'fixed_status_values': '\n'.join(scope.fixed_status_values),
            'closed_status_values': '\n'.join(scope.closed_status_values),
            'terminal_excluded_status_values': '\n'.join(scope.terminal_excluded_status_values),
            'fixed_resolution_values': '\n'.join(scope.fixed_resolution_values),
            'closed_resolution_values': '\n'.join(scope.closed_resolution_values),
            'reopen_status_values': '\n'.join(scope.reopen_status_values),
            'severity_field': scope.severity_field,
            'critical_high_values': critical_high_values,
            'medium_low_values': '\n'.join(scope.medium_low_values),
            'component_field': scope.component_field,
            'owner_field': scope.owner_field,
            'team_field': scope.team_field,
            'milestone_field': scope.milestone_field,
            'fix_version_field': scope.fix_version_field,
            'package_version_field': scope.package_version_field,
            'display_fields': '\n'.join(scope.display_fields),
            'timezone': scope.timezone,
            'bucket_granularity': scope.bucket_granularity,
            'enabled': 'on',
        }

    def _measure_scope_config_provider_tabs(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'desktop': self._measure_scope_config_provider_tabs_viewport(browser, html, 1440, 900),
                'phone': self._measure_scope_config_provider_tabs_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_config_dirty_state(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                initial_dirty_fields = page.locator('.is-dirty-field').count()
                page.fill('#scope-name', 'Unsaved scope name')
                return page.evaluate("""
                    initialDirtyFields => {
                        const field = document.querySelector('#scope-name');
                        const shell = field.closest('.scope-config-form-field');
                        const label = document.querySelector('label[for="scope-name"]');
                        const banner = document.querySelector('[data-dirty-banner]');
                        const cancel = document.querySelector('.scope-editor-actions button[value="discard"]');
                        const actions = document.querySelector('.scope-editor-actions');
                        const heights = Array.from(actions.querySelectorAll('.button'))
                            .map(button => Math.round(button.getBoundingClientRect().height))
                            .filter(height => height > 0);
                        return {
                            initial_dirty_fields: initialDirtyFields,
                            dirty_field_highlighted: shell.classList.contains('is-dirty-field'),
                            dirty_control_highlighted: field.classList.contains('is-dirty-control'),
                            dirty_banner_visible: banner ? !banner.classList.contains('is-hidden') : false,
                            dirty_label_text: label ? label.innerText : '',
                            cancel_button_visible: cancel ? cancel.getBoundingClientRect().height > 0 : false,
                            action_button_height_delta: Math.max(...heights) - Math.min(...heights),
                            action_gap_px: Math.round(parseFloat(getComputedStyle(actions).columnGap || getComputedStyle(actions).gap || '0')),
                            page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        };
                    }
                """, initial_dirty_fields)
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_required_validation(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                page.click('.scope-editor-actions button[value="save_draft"]')
                save_draft = page.evaluate("""
                    () => ({
                        missing_names: Array.from(document.querySelectorAll('.is-required-missing-control')).map(field => field.name),
                        summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
                        focused_id: document.activeElement.id,
                        messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
                    })
                """)
                page.fill('#scope-name', 'Required visual scope')
                page.fill('#scope-jql', 'project = STDEL')
                page.fill('#scope-bug-types', 'Bug')
                page.click('.scope-editor-actions button[value="save_enable"]')
                enable = page.evaluate("""
                    () => ({
                        missing_names: Array.from(document.querySelectorAll('.is-required-missing-control')).map(field => field.name),
                        summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
                        focused_id: document.activeElement.id,
                        messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
                    })
                """)
                return {
                    'save_draft_missing_names': save_draft['missing_names'],
                    'save_draft_summary_visible': save_draft['summary_visible'],
                    'save_draft_focused_id': save_draft['focused_id'],
                    'save_draft_messages': save_draft['messages'],
                    'enable_missing_names': enable['missing_names'],
                    'enable_summary_visible': enable['summary_visible'],
                    'enable_focused_id': enable['focused_id'],
                    'enable_messages': enable['messages'],
                }
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_config_provider_tabs_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const shell = document.querySelector('.scope-config-provider-panel.provider-tab-shell');
                    const tabBody = document.querySelector('.provider-tab-body');
                    const contextGrid = document.querySelector('.scope-provider-grid');
                    const detailPanel = document.querySelector('.scope-provider-detail-panel');
                    const profileSelect = document.querySelector('select[name="profile_id"]');
                    const selectedTab = document.querySelector('.provider-tab-list [aria-selected="true"]');
                    const selectedCheck = selectedTab ? selectedTab.querySelector('.provider-tab-check') : null;
                    const providerChoiceHeights = Array.from(document.querySelectorAll('.provider-tab-list .provider-setup-choice'))
                        .map(choice => Math.round(choice.getBoundingClientRect().height));
                    const formControlHeights = Array.from(document.querySelectorAll('.scope-config-form-field .input, .scope-config-form-field select'))
                        .map(control => Math.round(control.getBoundingClientRect().height))
                        .filter(height => height > 0);
                    const maxHeight = values => values.length ? Math.max(...values) : 0;
                    const minHeight = values => values.length ? Math.min(...values) : 0;
                    const shellBorderColor = shell ? getComputedStyle(shell).borderLeftColor : '';
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        tab_count: document.querySelectorAll('.provider-tab-list [role="tab"]').length,
                        selected_check_visible: selectedCheck ? selectedCheck.getBoundingClientRect().width >= 14 : false,
                        tab_shell_wraps_provider_content: Boolean(
                            shell && contextGrid && detailPanel && profileSelect
                            && shell.contains(contextGrid)
                            && shell.contains(detailPanel)
                            && shell.contains(profileSelect)
                        ),
                        tab_body_visible: tabBody ? tabBody.getBoundingClientRect().height > 0 : false,
                        selected_tab_attached_to_body: Boolean(
                            selectedTab && tabBody
                            && Math.abs(selectedTab.getBoundingClientRect().bottom - tabBody.getBoundingClientRect().top) <= 2
                        ),
                        selected_tab_is_hsdes: selectedTab ? selectedTab.textContent.includes('HSD-ES') : false,
                        shell_border_is_blue: shellBorderColor === 'rgb(28, 126, 214)',
                        detail_panel_left_border_width: detailPanel ? Math.round(parseFloat(getComputedStyle(detailPanel).borderLeftWidth)) : 0,
                        provider_choice_max_height: maxHeight(providerChoiceHeights),
                        scope_form_control_height_delta: maxHeight(formControlHeights) - minHeight(formControlHeights),
                    };
                }
            """)
        finally:
            page.close()

    def _measure_scope_library_row_actions(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        main_js = (static_dir / 'js' / 'main.js').read_text(encoding='utf-8')
        html = html.replace(
            '</head>',
            f'<style>{vendor_css}\n{main_css}</style></head>',
        ).replace(
            '</body>',
            f'<script>{main_js}</script></body>',
        )
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            import_file_visible_initial = page.locator('.scope-import-panel').is_visible()
            page.locator('.scope-import-menu summary').click()
            import_file_visible_after_open = page.locator('.scope-import-panel').is_visible()
            page.locator('.scope-import-menu').evaluate('menu => { menu.open = false; }')
            page.locator('.scope-library-header .title').hover()
            page.wait_for_timeout(180)
            help_result = page.evaluate("""
                () => {
                    const helpTip = document.querySelector('.help-tip');
                    const iconHelpTip = document.querySelector('.help-tip.is-icon');
                    const helpTipBubble = helpTip ? getComputedStyle(helpTip, '::after') : null;
                    const helpTipRect = helpTip ? helpTip.getBoundingClientRect() : null;
                    const iconHelpTipRect = iconHelpTip ? iconHelpTip.getBoundingClientRect() : null;
                    return {
                        help_tip_visible_on_hover: helpTipBubble ? Number(helpTipBubble.opacity) > 0.9 : false,
                        help_tip_width: helpTipRect ? Math.round(helpTipRect.width) : 0,
                        icon_help_tip_width: iconHelpTipRect ? Math.round(iconHelpTipRect.width) : 0,
                    };
                }
            """)
            page.locator('.scope-row-menu summary').first.click()
            result = page.evaluate("""
                () => {
                    const actions = document.querySelector('tbody tr .scope-primary-actions');
                    const primaryButtons = Array.from(actions.querySelectorAll(':scope > .button, :scope > .scope-row-menu > summary.button'));
                    const primaryRects = primaryButtons.map(button => button.getBoundingClientRect());
                    const panel = actions.querySelector('.workbench-menu-panel').getBoundingClientRect();
                    const cell = actions.closest('td').getBoundingClientRect();
                    const menu = actions.querySelector('.scope-row-menu');
                    const archiveButton = actions.querySelector('button[value="disable"]');
                    const archiveRect = archiveButton ? archiveButton.getBoundingClientRect() : null;
                    return {
                        same_row: primaryRects.length >= 2 && Math.abs(primaryRects[0].top - primaryRects[1].top) <= 1,
                        primary_heights: Array.from(new Set(primaryRects.map(rect => Math.round(rect.height)))).sort((a, b) => a - b),
                        primary_widths: Array.from(new Set(primaryRects.map(rect => Math.round(rect.width)))).sort((a, b) => a - b),
                        panel_width: Math.round(panel.width),
                        action_cell_width: Math.round(cell.width),
                        archive_action_visible: archiveRect !== null && archiveRect.width > 0 && archiveRect.height > 0,
                        horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        open_after_summary_click: menu.open,
                    };
                }
            """)
            result.update(help_result)
            result['import_file_visible_initial'] = import_file_visible_initial
            result['import_file_visible_after_open'] = import_file_visible_after_open
            page.mouse.click(20, 20)
            result['open_after_blank_click'] = page.locator('.scope-row-menu').first.evaluate('menu => menu.open')
            page.locator('.scope-row-menu summary').first.click()
            page.keyboard.press('Escape')
            result['open_after_escape'] = page.locator('.scope-row-menu').first.evaluate('menu => menu.open')
            return result
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _measure_scope_library_delete_confirmation(self, html, confirmation):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            page.locator('button[value="delete_archived"]').evaluate("button => { button.closest('details').open = true; }")
            page.evaluate("""
                confirmation => {
                    window.__deleteResult = {
                        submitted: false,
                        confirm_message: '',
                        prompt_message: '',
                        prompt_default: '',
                        posted_confirmation: '',
                    };
                    window.confirm = message => {
                        window.__deleteResult.confirm_message = message;
                        return true;
                    };
                    window.prompt = (message, defaultValue) => {
                        window.__deleteResult.prompt_message = message;
                        window.__deleteResult.prompt_default = defaultValue || '';
                        return confirmation;
                    };
                    const form = document.querySelector('button[value="delete_archived"]').closest('form');
                    form.addEventListener('submit', event => {
                        event.preventDefault();
                        window.__deleteResult.submitted = true;
                        window.__deleteResult.posted_confirmation = new FormData(form).get('delete_confirmation') || '';
                    });
                }
            """, confirmation)
            page.locator('button[value="delete_archived"]').click()
            return page.evaluate("() => window.__deleteResult")
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _measure_scope_library_responsive_table(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'wide': self._measure_scope_library_viewport(browser, html, 1920, 900),
                'desktop': self._measure_scope_library_viewport(browser, html, 1532, 768),
                'medium': self._measure_scope_library_viewport(browser, html, 1180, 820),
                'phone': self._measure_scope_library_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_library_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const rows = Array.from(document.querySelectorAll('.scope-library-table tbody tr'));
                    const bodyRowHeights = rows.map(row => Math.round(row.getBoundingClientRect().height));
                    const firstActions = document.querySelector('tbody tr .scope-primary-actions');
                    const actionRects = firstActions
                        ? Array.from(firstActions.querySelectorAll(':scope > .button, :scope > form .button, :scope > .scope-row-menu > summary.button')).map(button => button.getBoundingClientRect())
                        : [];
                    const hashCell = document.querySelector('.scope-library-table tbody td.scope-col-hash');
                    const ipCell = document.querySelector('.scope-library-table tbody td.scope-col-ip');
                    const projectCell = document.querySelector('.scope-library-table tbody td.scope-col-project');
                    const thead = document.querySelector('.scope-library-table thead');
                    const firstCell = document.querySelector('.scope-library-table tbody td');
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        table_horizontal_overflow: document.querySelector('.scope-library-table-box').scrollWidth > document.querySelector('.scope-library-table-box').clientWidth + 1,
                        max_body_row_height: Math.max(...bodyRowHeights),
                        actions_wrap: actionRects.length >= 2 && Math.abs(actionRects[0].top - actionRects[1].top) > 1,
                        hash_column_display: hashCell ? getComputedStyle(hashCell).display : '',
                        ip_column_display: ipCell ? getComputedStyle(ipCell).display : '',
                        project_column_display: projectCell ? getComputedStyle(projectCell).display : '',
                        thead_display: thead ? getComputedStyle(thead).display : '',
                        first_cell_display: firstCell ? getComputedStyle(firstCell).display : '',
                    };
                }
            """)
        finally:
            page.close()

    def _scope_library_browser_html(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        main_js = (static_dir / 'js' / 'main.js').read_text(encoding='utf-8')
        return html.replace(
            '</head>',
            f'<style>{vendor_css}\n{main_css}</style></head>',
        ).replace(
            '</body>',
            f'<script>{main_js}</script></body>',
        )
