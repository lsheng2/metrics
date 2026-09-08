import json
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig, ProviderProfileConfig


class TestProviderSetupViews(TestCase):
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

    def _profile_payload(self):
        return {
            'action': 'save_draft',
            'id': '',
            'profile_id': 'new-provider-profile',
            'provider_id': 'jira',
            'display_name': 'New Provider Profile',
            'lifecycle_state': 'draft',
            'mapping_version': '1',
            'source_population': json.dumps({'native_query_text': 'project = NEW'}),
            'scope_labels': json.dumps({'ip': 'new-ip', 'project_or_product': 'new-project'}),
            'field_bindings': json.dumps({'severity': {'native_field': 'priority'}}),
            'value_mappings': json.dumps({'bug_type_values': ['Bug']}),
            'chart_bindings': json.dumps({'open_bug_trend': {'support_status': 'supported'}}),
            'sync_policy': json.dumps({'live_sync': 'supported'}),
            'readiness_policy': json.dumps({'ready_status': 'ready'}),
        }

    def _hsdes_profile_payload(self):
        payload = self._profile_payload()
        payload.update({
            'profile_id': 'new-hsdes-profile',
            'provider_id': 'hsdes',
            'display_name': 'New HSD-ES Profile',
            'connection_base_url': 'https://hsdes-api.intel.com/rest',
            'connection_auth_mode': 'kerberos',
            'credential_ref': 'profile:local',
            'source_population': json.dumps({'provider_id': 'hsdes', 'ownership_type': 'provider_owned_saved_query'}),
            'field_bindings': json.dumps({'item_id': {'native_field': 'id'}}),
            'chart_bindings': json.dumps({'component_bug': {'support_status': 'supported_from_seed_facts'}}),
        })
        return payload

    def _measure_provider_setup_layout(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'desktop': self._measure_provider_setup_viewport(browser, html, 1440, 900),
                'phone': self._measure_provider_setup_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_provider_setup_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const editor = document.querySelector('.provider-setup-editor');
                    const advanced = document.querySelector('.provider-advanced-config');
                    const tableBox = document.querySelector('.provider-profile-table-box');
                    const shell = document.querySelector('.provider-tab-shell');
                    const tabBody = document.querySelector('.provider-tab-body');
                    const contextPanel = document.querySelector('.provider-context-panel');
                    const identityRow = document.querySelector('.provider-identity-row');
                    const actions = document.querySelector('.provider-editor-actions');
                    const selectedCheck = document.querySelector('.provider-setup-choice.is-selected .provider-tab-check');
                    const selectedTab = document.querySelector('.provider-tab-list [aria-selected="true"]');
                    const primaryButtons = Array.from(document.querySelectorAll('.provider-row-primary-actions > .button, .provider-row-primary-actions > .provider-row-menu > summary.button'));
                    const primaryButtonHeights = primaryButtons
                        .map(button => Math.round(button.getBoundingClientRect().height))
                        .filter(height => height > 0);
                    const providerChoiceHeights = Array.from(document.querySelectorAll('.provider-setup-choice'))
                        .map(choice => Math.round(choice.getBoundingClientRect().height));
                    const formControlHeights = Array.from(document.querySelectorAll('.provider-form-field .input, .provider-form-field select'))
                        .map(control => Math.round(control.getBoundingClientRect().height))
                        .filter(height => height > 0);
                    const maxHeight = values => values.length ? Math.max(...values) : 0;
                    const minHeight = values => values.length ? Math.min(...values) : 0;
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        table_horizontal_overflow: tableBox ? tableBox.scrollWidth > tableBox.clientWidth + 1 : false,
                        inventory_visible: tableBox ? tableBox.getBoundingClientRect().height > 0 : false,
                        editor_visible: editor ? editor.getBoundingClientRect().height > 0 : false,
                        provider_choice_count: document.querySelectorAll('.scope-provider-choice').length,
                        advanced_json_open: advanced ? advanced.open : false,
                        primary_action_button_height_delta: maxHeight(primaryButtonHeights) - minHeight(primaryButtonHeights),
                        provider_choice_max_height: maxHeight(providerChoiceHeights),
                        selected_check_visible: selectedCheck ? selectedCheck.getBoundingClientRect().width >= 14 : false,
                        tab_shell_wraps_context: Boolean(shell && contextPanel && identityRow && shell.contains(contextPanel) && shell.contains(identityRow)),
                        tab_body_visible: tabBody ? tabBody.getBoundingClientRect().height > 0 : false,
                        selected_tab_attached_to_body: Boolean(
                            selectedTab && tabBody
                            && Math.abs(selectedTab.getBoundingClientRect().bottom - tabBody.getBoundingClientRect().top) <= 2
                        ),
                        tab_shell_wraps_editor_controls: Boolean(shell && advanced && actions && shell.contains(advanced) && shell.contains(actions)),
                        context_panel_left_border_width: contextPanel ? Math.round(parseFloat(getComputedStyle(contextPanel).borderLeftWidth)) : 0,
                        provider_form_control_height_delta: maxHeight(formControlHeights) - minHeight(formControlHeights),
                    };
                }
            """)
        finally:
            page.close()

    def _provider_setup_browser_html(self, html):
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

    def _measure_provider_auth_visibility(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                return page.evaluate("""
                    () => {
                        const activePanel = document.querySelector('.provider-auth-panel:not(.is-hidden)');
                        const inactiveInputs = Array.from(document.querySelectorAll('.provider-auth-panel.is-hidden input'));
                        const inactiveInputsDisabledBeforeSwitch = inactiveInputs.every(input => input.disabled);
                        const select = document.querySelector('[data-provider-auth-select]');
                        let cloudEmailVisibleAfterSwitch = false;
                        let cloudEmailValueAfterSwitch = '';
                        if (select) {
                            select.value = 'cloud_basic';
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            const cloudEmail = document.querySelector('#provider-connection-email');
                            cloudEmailVisibleAfterSwitch = Boolean(
                                cloudEmail
                                && !cloudEmail.disabled
                                && !cloudEmail.closest('.provider-auth-panel').classList.contains('is-hidden')
                            );
                            cloudEmailValueAfterSwitch = cloudEmail ? cloudEmail.value : '';
                        }
                        return {
                            initial_active_text: activePanel ? activePanel.innerText : '',
                            inactive_inputs_disabled: inactiveInputsDisabledBeforeSwitch,
                            cloud_email_visible_after_switch: cloudEmailVisibleAfterSwitch,
                            cloud_email_value_after_switch: cloudEmailValueAfterSwitch,
                        };
                    }
                """)
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_connection_test_result_layout(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                return page.evaluate("""
                    () => {
                        const result = document.querySelector('#provider-connection-test-result');
                        const actions = document.querySelector('.provider-editor-actions');
                        return {
                            result_visible: result ? result.getBoundingClientRect().height > 0 : false,
                            result_before_actions: Boolean(
                                result && actions
                                && result.getBoundingClientRect().bottom <= actions.getBoundingClientRect().top + 1
                            ),
                            result_text: result ? result.innerText : '',
                        };
                    }
                """)
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_provider_dirty_state(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                initial_dirty_fields = page.locator('.is-dirty-field').count()
                page.fill('#provider-hsdes-saved-query-id', '15017652869')
                dirty_state = page.evaluate("""
                    () => {
                        const field = document.querySelector('#provider-hsdes-saved-query-id');
                        const shell = field.closest('.provider-form-field');
                        const label = document.querySelector('label[for="provider-hsdes-saved-query-id"]');
                        const banner = document.querySelector('[data-dirty-banner]');
                        const cancel = document.querySelector('[data-dirty-reset]');
                        const actions = document.querySelector('.provider-editor-actions');
                        const heights = Array.from(actions.querySelectorAll('.button'))
                            .map(button => Math.round(button.getBoundingClientRect().height))
                            .filter(height => height > 0);
                        return {
                            dirty_field_highlighted: shell.classList.contains('is-dirty-field'),
                            dirty_control_highlighted: field.classList.contains('is-dirty-control'),
                            dirty_banner_visible: banner ? !banner.classList.contains('is-hidden') : false,
                            dirty_label_text: label ? label.innerText : '',
                            cancel_button_visible: cancel ? cancel.getBoundingClientRect().height > 0 : false,
                            action_button_height_delta: Math.max(...heights) - Math.min(...heights),
                            action_gap_px: Math.round(parseFloat(getComputedStyle(actions).columnGap || getComputedStyle(actions).gap || '0')),
                        };
                    }
                """)
                page.click('[data-dirty-reset]')
                after_cancel = page.evaluate("""
                    () => {
                        const banner = document.querySelector('[data-dirty-banner]');
                        return {
                            after_cancel_value: document.querySelector('#provider-hsdes-saved-query-id').value,
                            after_cancel_dirty_fields: document.querySelectorAll('.is-dirty-field').length,
                            after_cancel_banner_visible: banner ? !banner.classList.contains('is-hidden') : false,
                        };
                    }
                """)
                return {'initial_dirty_fields': initial_dirty_fields, **dirty_state, **after_cancel}
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_provider_required_validation(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                page.click('.provider-editor-actions button[value="save_draft"]')
                save_draft = page.evaluate("""
                    () => ({
                        missing_names: Array.from(document.querySelectorAll('.is-required-missing-control')).map(field => field.name),
                        summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
                        focused_id: document.activeElement.id,
                        messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
                    })
                """)
                page.fill('#provider-profile-id', 'hsdes-required-test')
                page.fill('#provider-display-name', 'HSD-ES Required Test')
                page.click('.provider-editor-actions button[value="test_connection"]')
                test_connection = page.evaluate("""
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
                    'test_connection_missing_names': test_connection['missing_names'],
                    'test_connection_summary_visible': test_connection['summary_visible'],
                    'test_connection_focused_id': test_connection['focused_id'],
                    'test_connection_messages': test_connection['messages'],
                }
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()
