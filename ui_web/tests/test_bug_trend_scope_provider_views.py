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


from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport


class TestBugTrendScopeProviderViews(BugTrendScopeConfigViewTestSupport, TestCase):
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
