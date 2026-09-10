import json
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig, ProviderProfileConfig


from ui_web.tests.provider_setup_view_test_support import ProviderSetupViewTestSupport


class TestProviderSetupViews(ProviderSetupViewTestSupport, TestCase):
    def test_shouldRenderProviderSetupMenuAndProfileInventory(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Provider Setup', content)
        self.assertIn('New Profile', content)
        self.assertIn('chiplet-2a-jira', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('scope-provider-tag is-provider-green', content)
        self.assertIn('scope-provider-tag is-provider-blue', content)
        self.assertIn('Create Scope', content)
        self.assertIn('Export', content)
        self.assertIn('Assign existing scope', content)
        self.assertIn('New users should usually choose Create Scope instead.', content)
        self.assertNotIn('>Bind</button>', content)
        self.assertNotIn('provider-setup-editor', content)

    def test_shouldRenderProviderFirstEditorForHsdesProfile(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'hsdes',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Provider Profile Config', content)
        self.assertIn('New profile draft', content)
        self.assertIn('Profile Editor', content)
        self.assertNotIn('provider-profile-table-box', content)
        self.assertIn('id="provider-profile-id" name="profile_id" value=""', content)
        self.assertIn('id="provider-display-name" name="display_name" value=""', content)
        self.assertIn('id="provider-connection-base-url" name="connection_base_url" value=""', content)
        self.assertIn('<option value="" selected>Choose authentication method</option>', content)
        self.assertNotIn('value="hsdes-default"', content)
        self.assertNotIn('value="HSD-ES Default"', content)
        self.assertIn('provider-setup-choice is-provider-blue is-selected', content)
        self.assertIn('provider-tab-check', content)
        self.assertIn('provider-tab-shell is-provider-blue', content)
        self.assertIn('HSD-ES metadata refresh is not wired', content)
        self.assertIn('Base URL', content)
        self.assertIn('Authentication method', content)
        self.assertIn('System status', content)
        self.assertNotIn('Credential ref', content)
        self.assertIn('Authentication Details', content)
        self.assertIn('Clear saved credentials', content)
        self.assertNotIn('Onboarding status', content)
        self.assertIn('HSD-ES Connection Probe', content)
        self.assertIn('Dashboard profile key', content)
        self.assertIn('This is not the HSD-ES saved query id used by Test Connection.', content)
        self.assertIn('HSD-ES saved query id', content)
        self.assertIn('name="hsdes_saved_query_id"', content)
        self.assertIn('name="hsdes_tenant"', content)
        self.assertIn('name="hsdes_subject"', content)
        self.assertIn('placeholder="15017652869"', content)
        self.assertIn('placeholder="https://hsdes-api.intel.com/rest"', content)
        self.assertIn('Not set', content)
        self.assertIn('Windows Integrated Auth', content)
        self.assertIn('Your username', content)
        self.assertNotIn('provider-connection_settings', content)
        self.assertIn('Field Bindings', content)
        self.assertIn('Scope Config owns project JQL, saved query id, product and milestone filters.', content)
        self.assertIn('Native type, status and severity values fill bug type, open/fixed/closed, critical/high and medium/low elements.', content)
        self.assertIn('Chart bindings and readiness policy decide Workbench, Data Health, AI and Grafana availability.', content)

    def test_shouldAllowProviderSetupDraftCreationFromGithubTemplate(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'github',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('provider-setup-choice is-provider-purple is-selected', content)
        self.assertIn('provider-tab-shell is-provider-purple', content)
        self.assertIn('name="provider_id" value="github"', content)
        self.assertIn('GitHub metadata is template-only until a provider profile and adapter are registered.', content)
        self.assertIn('id="provider-profile-id" name="profile_id" value=""', content)
        self.assertIn('id="provider-display-name" name="display_name" value=""', content)
        self.assertIn('placeholder="https://api.github.com"', content)
        self.assertIn('<option value="" selected>Choose authentication method</option>', content)

    def test_shouldRenderOnlyCurrentProviderAuthenticationFields(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'jira',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('API token / PAT', content)
        self.assertIn('Email + API token', content)
        self.assertNotIn('HSD-ES username', content)
        self.assertNotIn('HSD-ES password', content)
        self.assertNotIn('Username + password', content)
        self.assertNotIn('Bearer token', content)
        self.assertNotIn('Personal access token</strong>', content)

    def test_shouldKeepProviderSetupUsableAcrossDesktopAndPhoneInBrowser(self):
        # Given
        self.client.post(reverse('ui_web:provider_setup'), self._profile_payload(), follow=True)

        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'profile_id': 'new-provider-profile',
        })
        results = self._measure_provider_setup_layout(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertFalse(results['desktop']['page_horizontal_overflow'])
        self.assertFalse(results['desktop']['table_horizontal_overflow'])
        self.assertFalse(results['phone']['page_horizontal_overflow'])
        self.assertTrue(results['desktop']['editor_visible'])
        self.assertTrue(results['phone']['editor_visible'])
        self.assertFalse(results['desktop']['inventory_visible'])
        self.assertFalse(results['phone']['inventory_visible'])
        self.assertGreaterEqual(results['desktop']['provider_choice_count'], 3)
        self.assertGreaterEqual(results['phone']['provider_choice_count'], 3)
        self.assertFalse(results['desktop']['advanced_json_open'])
        self.assertFalse(results['phone']['advanced_json_open'])
        self.assertLessEqual(results['desktop']['primary_action_button_height_delta'], 1)
        self.assertLessEqual(results['desktop']['provider_choice_max_height'], 82)
        self.assertTrue(results['desktop']['selected_check_visible'])
        self.assertTrue(results['desktop']['tab_shell_wraps_context'])
        self.assertTrue(results['desktop']['tab_body_visible'])
        self.assertTrue(results['desktop']['selected_tab_attached_to_body'])
        self.assertTrue(results['desktop']['tab_shell_wraps_editor_controls'])
        self.assertLessEqual(results['desktop']['context_panel_left_border_width'], 1)
        self.assertLessEqual(results['desktop']['provider_form_control_height_delta'], 1)
        self.assertLessEqual(results['phone']['provider_form_control_height_delta'], 1)

    def test_shouldMarkUnsavedProviderFieldAndCancelEditingInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'hsdes',
        })
        results = self._measure_provider_dirty_state(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, results['initial_dirty_fields'])
        self.assertTrue(results['dirty_field_highlighted'])
        self.assertTrue(results['dirty_control_highlighted'])
        self.assertTrue(results['dirty_banner_visible'])
        self.assertIn('Unsaved *', results['dirty_label_text'])
        self.assertTrue(results['cancel_button_visible'])
        self.assertLessEqual(results['action_button_height_delta'], 1)
        self.assertGreaterEqual(results['action_gap_px'], 8)
        self.assertEqual('', results['after_cancel_value'])
        self.assertEqual(0, results['after_cancel_dirty_fields'])
        self.assertFalse(results['after_cancel_banner_visible'])

    def test_shouldHighlightActionRequiredProviderFieldsInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'hsdes',
        })
        results = self._measure_provider_required_validation(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(['profile_id', 'display_name'], results['save_draft_missing_names'])
        self.assertTrue(results['save_draft_summary_visible'])
        self.assertEqual('provider-profile-id', results['save_draft_focused_id'])
        self.assertIn('Dashboard profile key is required before saving this profile.', results['save_draft_messages'])
        self.assertNotIn('connection_base_url', results['save_draft_missing_names'])
        self.assertEqual(
            ['connection_base_url', 'connection_auth_mode', 'hsdes_saved_query_id', 'hsdes_tenant', 'hsdes_subject'],
            results['test_connection_missing_names'],
        )
        self.assertTrue(results['test_connection_summary_visible'])
        self.assertEqual('provider-connection-base-url', results['test_connection_focused_id'])
        self.assertIn('HSD-ES saved query id is required for Test Connection.', results['test_connection_messages'])

    def test_shouldSaveProviderProfileDraftFromSetup(self):
        # When
        payload = self._profile_payload()
        payload['connection_base_url'] = 'settings:METRICS_JIRA_SERVER_URL'
        payload['connection_auth_mode'] = 'server_pat'
        payload['credential_ref'] = 'settings:METRICS_JIRA_API_TOKEN'
        payload['connection_email'] = 'jira-user@example.com'
        payload['connection_api_token'] = 'must-not-render'
        payload['connection_password'] = 'visible-password'
        payload['connection_token'] = 'hidden-bearer-token'
        payload['onboarding_status'] = 'ready'
        response = self.client.post(reverse('ui_web:provider_setup'), payload, follow=True)

        # Then
        profile = ProviderProfileConfig.objects.get(profile_id='new-provider-profile')
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_DRAFT, profile.lifecycle_state)
        self.assertEqual('server_pat', profile.connection_settings['auth_mode'])
        self.assertEqual('settings:METRICS_JIRA_API_TOKEN', profile.connection_settings['credential_ref'])
        self.assertEqual('must-not-render', profile.connection_settings['credentials']['api_token'])
        self.assertIn('Provider profile saved.', content)
        self.assertIn('new-provider-profile', content)
        self.assertNotIn('must-not-render', content)
        self.assertNotIn('hidden-bearer-token', content)
        self.assertIn('value="********"', content)
        self.assertNotIn('password', profile.connection_settings['credentials'])
        self.assertNotIn('token', profile.connection_settings['credentials'])
        self.assertNotIn('email', profile.connection_settings['credentials'])
        self.assertEqual('deployment_configured', profile.connection_settings['onboarding_status'])

    @patch('bug_metrics.app.api.provider_profile_connection_test.create_jira_client')
    def test_shouldTestProviderProfileConnectionWithoutSavingProfile(self, create_jira_client):
        # Given
        create_jira_client.return_value.get_server_info.return_value = {
            'serverTitle': 'Jira Test',
            'version': '10.0',
        }
        payload = self._profile_payload()
        payload['action'] = 'test_connection'
        payload['profile_id'] = 'transient-connection-profile'
        payload['connection_base_url'] = 'https://jira.profile.example'
        payload['connection_auth_mode'] = 'server_pat'
        payload['credential_ref'] = 'profile:local'
        payload['connection_api_token'] = 'secret-token'

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Connection test: success', content)
        self.assertIn('Jira connection succeeded.', content)
        self.assertIn('provider-connection-test-result', content)
        self.assertIn('Last test: success', content)
        self.assertNotIn('secret-token', content)
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='transient-connection-profile').exists())
        result_layout = self._measure_connection_test_result_layout(content)
        self.assertTrue(result_layout['result_visible'])
        self.assertTrue(result_layout['result_before_actions'])
        self.assertIn('Jira connection succeeded.', result_layout['result_text'])

    @patch('bug_metrics.app.api.provider_profile_connection_test.HsdesHttpClient')
    def test_shouldTestHsdesConnectionWithVisibleProbeFields(self, hsdes_client):
        # Given
        hsdes_client.return_value.execute_saved_query.return_value = {'total': 1, 'data': [{'id': '1'}]}
        payload = self._hsdes_profile_payload()
        payload['action'] = 'test_connection'
        payload['hsdes_saved_query_id'] = '15017652869'
        payload['hsdes_tenant'] = 'ip_fw_sw_sensing.tenant'
        payload['hsdes_subject'] = 'ip_fw_sw_sensing.bug'

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('HSD-ES Connection Probe', content)
        self.assertIn('value="15017652869"', content)
        self.assertIn('value="ip_fw_sw_sensing.tenant"', content)
        self.assertIn('value="ip_fw_sw_sensing.bug"', content)
        self.assertIn('Connection test: success', content)
        self.assertIn('HSD-ES saved-query probe succeeded.', content)
        self.assertNotIn('Advanced source settings', content)
        hsdes_client.return_value.execute_saved_query.assert_called_once_with(
            '15017652869',
            'ip_fw_sw_sensing.tenant',
            'ip_fw_sw_sensing.bug',
            ['id'],
            0,
            1,
        )

    def test_shouldRenderEnablementErrorsForMissingChartMappings(self):
        # Given
        payload = self._profile_payload()
        payload['action'] = 'enable_profile'
        payload['profile_id'] = 'missing-chart-mapping-ui'
        payload['field_bindings'] = json.dumps({'submitted_date': {'native_field': 'created'}})
        payload['chart_bindings'] = json.dumps({
            'open_bug_trend': {
                'support_status': 'supported',
                'required_canonical_fields': ['submitted_date', 'severity'],
            },
        })

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Provider profile was not saved.', content)
        self.assertIn('chart_bindings', content)
        self.assertIn('severity', content)
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='missing-chart-mapping-ui').exists())

    def test_shouldRenderManagedProfileEditFormWithPersistentId(self):
        # Given
        self.client.post(reverse('ui_web:provider_setup'), self._profile_payload(), follow=True)
        profile = ProviderProfileConfig.objects.get(profile_id='new-provider-profile')

        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'profile_id': 'new-provider-profile',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn(f'name="id" value="{profile.id}"', content)
        self.assertIn('New Provider Profile', content)

    @override_settings(
        METRICS_JIRA_SERVER_URL='https://jira.actual.example',
        METRICS_JIRA_AUTH_MODE='server_pat',
        METRICS_JIRA_EMAIL='actual-user@example.com',
        METRICS_JIRA_API_TOKEN='actual-token-value',
    )
    def test_shouldRenderSettingsBackedProfileWithResolvedDisplayValuesAndMaskedToken(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'profile_id': 'chiplet-2a-jira',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('https://jira.actual.example', content)
        self.assertIn('server_pat', content)
        self.assertIn('value="********"', content)
        self.assertNotIn('actual-token-value', content)
        auth_state = self._measure_provider_auth_visibility(content)
        self.assertIn('API token / PAT', auth_state['initial_active_text'])
        self.assertNotIn('actual-user@example.com', auth_state['initial_active_text'])
        self.assertTrue(auth_state['inactive_inputs_disabled'])
        self.assertTrue(auth_state['cloud_email_visible_after_switch'])
        self.assertEqual('actual-user@example.com', auth_state['cloud_email_value_after_switch'])

    @override_settings(
        METRICS_HSDES_API_BASE_URL='https://hsdes-api.actual.example/rest',
        METRICS_HSDES_AUTH_MODE='basic',
        METRICS_HSDES_USERNAME='actual-hsdes-user',
        METRICS_HSDES_PASSWORD='actual-hsdes-password',
    )
    def test_shouldMaskSettingsBackedHsdesPasswordInProfileEditor(self):
        # When
        response = self.client.get(reverse('ui_web:provider_setup'), {
            'profile_id': 'nvu-ttl-hsdes',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('https://hsdes-api.actual.example/rest', content)
        self.assertIn('actual-hsdes-user', content)
        self.assertIn('value="********"', content)
        self.assertNotIn('actual-hsdes-password', content)

    def test_shouldArchiveAndDeleteProviderProfileWithConfirmation(self):
        # Given
        self.client.post(reverse('ui_web:provider_setup'), self._profile_payload(), follow=True)

        # When
        archive_response = self.client.post(reverse('ui_web:provider_setup'), {
            'action': 'archive_profile',
            'profile_id': 'new-provider-profile',
        }, follow=True)
        delete_response = self.client.post(reverse('ui_web:provider_setup'), {
            'action': 'delete_archived_profile',
            'profile_id': 'new-provider-profile',
            'delete_confirmation': 'DELETE new-provider-profile',
        }, follow=True)

        # Then
        self.assertEqual(200, archive_response.status_code)
        self.assertEqual(200, delete_response.status_code)
        self.assertIn('Provider profile new-provider-profile archived.', archive_response.content.decode())
        self.assertIn('Archived provider profile new-provider-profile deleted.', delete_response.content.decode())
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='new-provider-profile').exists())

    def test_shouldRequireArchivedProviderProfileRestoreBeforeBindingScope(self):
        # Given
        scope = JiraScopeConfig.objects.create(name='Archived bind target', jql='project = STDEL', bug_type_values=['Bug'])
        ProviderProfileConfig.objects.create(
            profile_id='archived-bind-profile',
            provider_id='jira',
            display_name='Archived Bind Profile',
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_ARCHIVED,
            source_population={'native_query_text': 'project = STDEL'},
            field_bindings={'status': {'native_field': 'status'}},
            chart_bindings={'open_bug_trend': {'support_status': 'supported'}},
        )

        # When
        page_response = self.client.get(reverse('ui_web:provider_setup'))
        bind_response = self.client.post(reverse('ui_web:provider_setup'), {
            'action': 'bind_scope',
            'profile_id': 'archived-bind-profile',
            'scope_id': str(scope.id),
        }, follow=True)

        # Then
        page_content = page_response.content.decode()
        self.assertEqual(200, page_response.status_code)
        self.assertIn('Restore this profile before binding scopes.', page_content)
        self.assertNotIn('Scope to bind to archived-bind-profile', page_content)
        self.assertEqual(200, bind_response.status_code)
        self.assertIn('Provider profile archived-bind-profile is not available.', bind_response.content.decode())
        self.assertFalse(BugTrendScopeProviderBinding.objects.filter(scope=scope).exists())

    def test_shouldShowBindingErrorWhenArchivedProfileBindIsPostedDirectly(self):
        # Given
        scope = JiraScopeConfig.objects.create(name='Direct archived bind target', jql='project = STDEL', bug_type_values=['Bug'])
        ProviderProfileConfig.objects.create(
            profile_id='direct-archived-profile',
            provider_id='jira',
            display_name='Direct Archived Profile',
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_ARCHIVED,
            source_population={'native_query_text': 'project = STDEL'},
            field_bindings={'status': {'native_field': 'status'}},
            chart_bindings={'open_bug_trend': {'support_status': 'supported'}},
        )

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), {
            'action': 'bind_scope',
            'profile_id': 'direct-archived-profile',
            'scope_id': str(scope.id),
        }, follow=True)

        # Then
        self.assertEqual(200, response.status_code)
        self.assertIn('Provider profile direct-archived-profile is not available.', response.content.decode())
        self.assertFalse(BugTrendScopeProviderBinding.objects.filter(scope=scope).exists())

    def test_shouldExportAndImportProviderProfilePackage(self):
        # Given
        self.client.post(reverse('ui_web:provider_setup'), self._profile_payload(), follow=True)

        # When
        export_response = self.client.get(reverse('ui_web:provider_setup'), {
            'export_profile_id': 'new-provider-profile',
        })
        upload = SimpleUploadedFile('provider-profile.json', export_response.content, content_type='application/json')
        import_response = self.client.post(reverse('ui_web:provider_setup'), {
            'action': 'import_profile',
            'profile_package': upload,
        }, follow=True)

        # Then
        package = export_response.json()
        self.assertEqual(200, export_response.status_code)
        self.assertEqual('metrics.provider-profile', package['format'])
        self.assertIn('credentials', package['excludes'])
        self.assertEqual(200, import_response.status_code)
        self.assertTrue(ProviderProfileConfig.objects.filter(profile_id='new-provider-profile-imported').exists())
        self.assertIn('Imported provider profile new-provider-profile-imported as draft.', import_response.content.decode())

    def test_shouldBindExistingScopeFromProviderSetup(self):
        # Given
        scope = JiraScopeConfig.objects.create(name='Bind target scope', jql='project = STDEL', bug_type_values=['Bug'])

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), {
            'action': 'bind_scope',
            'profile_id': 'chiplet-2a-jira',
            'scope_id': str(scope.id),
        }, follow=True)

        # Then
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(200, response.status_code)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertIn('Scope binding saved.', response.content.decode())

    def test_shouldHandoffProfileToScopeConfigWithSafeDefaults(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('NVU', content)
        self.assertIn('NVU1.0_TTL', content)
        self.assertIn('15017652869', content)
        self.assertIn('critical', content)

    def test_shouldBindNewlyCreatedManagedProfileWhenCreatingScopeFromProviderSetup(self):
        # Given
        profile_payload = self._profile_payload()
        profile_payload['action'] = 'enable_profile'
        profile_payload['profile_id'] = 'fresh-managed-profile'
        profile_payload['display_name'] = 'Fresh Managed Profile'
        self.client.post(reverse('ui_web:provider_setup'), profile_payload, follow=True)

        # When
        handoff_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'jira',
            'profile_id': 'fresh-managed-profile',
        })
        save_response = self.client.post(reverse('ui_web:bug_trend_scope_config'), {
            'action': 'save_draft',
            'id': '',
            'name': 'fresh-managed-profile',
            'ip': 'new-ip',
            'project_label': 'new-project',
            'jql': 'project = NEW',
            'bug_type_values': 'Bug',
            'open_status_values': 'Open',
            'fixed_status_values': 'Fixed',
            'closed_status_values': 'Closed',
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
            'profile_id': 'fresh-managed-profile',
        }, follow=True)

        # Then
        scope = JiraScopeConfig.objects.get(name='fresh-managed-profile')
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        handoff_content = handoff_response.content.decode()
        self.assertEqual(200, handoff_response.status_code)
        self.assertIn('fresh-managed-profile (jira)', handoff_content)
        self.assertIn('option value="fresh-managed-profile" selected', handoff_content)
        self.assertEqual(200, save_response.status_code)
        self.assertEqual('fresh-managed-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertIn('fresh-managed-profile', save_response.content.decode())
