import json
from contextlib import ExitStack
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from forecast.app.domain.model.enums import TaskScope
from playwright.sync_api import sync_playwright
from sd_metrics_lib.utils.enums import HealthStatus

from bug_metrics.models import (
    BugTrendBucket,
    BugTrendBucketIssue,
    BugTrendCalculationRun,
    BugTrendScopeProviderBinding,
    JiraScopeConfig,
    ProviderProfileConfig,
)
from ui_web.data.member_data import MemberGroupData
from ui_web.data.pull_request_data import (
    ApprovalData,
    LinkedTaskData,
    PersonActivitySummaryData,
    PullRequestData,
)
from ui_web.data.task_data import (
    AssigneeData,
    AssignmentData,
    ForecastData,
    LinkedPullRequestData,
    ReleaseData,
    SystemMetadataData,
    TaskData,
    TimeTrackingData,
)
from ui_web.data.task_forecast_data import (
    TaskForecastBreakdownItem,
    TaskForecastParamsData,
    TaskForecastRequestData,
    TaskForecastSummaryData,
)
from ui_web.data.velocity_threshold_data import VelocityThresholdsData
from ui_web.data.velocity_task_detail_data import DeveloperVelocitySummary, TaskVelocityData


from ui_web.tests.ui_design_browser_metrics_support import UiDesignBrowserMetricsSupport


class TestUiDesignMonkeyJourney(UiDesignBrowserMetricsSupport, TestCase):
    def test_shouldSupportMonkeyUserProviderProfileScopeWorkbenchJourney(self):
        new_jira_page = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'jira',
        })
        self.assertIn('id="provider-profile-id" name="profile_id" value=""', new_jira_page.content.decode())
        self.assertIn('provider-setup-choice is-provider-green is-selected', new_jira_page.content.decode())
        profile_required_state = self._measure_required_submit(
            new_jira_page.content.decode(),
            'button[name="action"][value="test_connection"]',
        )
        self.assertIn('connection_base_url', profile_required_state['invalid_field_names'])
        self.assertEqual(
            len(profile_required_state['invalid_field_names']),
            profile_required_state['invalid_aria_count'],
        )
        self.assertGreater(profile_required_state['missing_shell_count'], 0)
        self.assertTrue(profile_required_state['summary_visible'])

        jira_payload = self._jira_profile_payload('monkey-jira-profile')
        with patch('bug_metrics.app.api.provider_profile_connection_test.create_jira_client') as create_jira_client:
            create_jira_client.return_value.get_server_info.return_value = {
                'serverTitle': 'Monkey Jira',
                'version': '10.0',
            }
            test_response = self.client.post(reverse('ui_web:provider_setup'), {
                **jira_payload,
                'action': 'test_connection',
                'connection_api_token': 'secret-jira-token',
            })
        self.assertEqual(200, test_response.status_code)
        test_content = test_response.content.decode()
        self.assertIn('Connection test: success', test_content)
        self.assertIn('Jira connection succeeded.', test_content)
        self.assertNotIn('secret-jira-token', test_content)

        save_profile_response = self.client.post(reverse('ui_web:provider_setup'), jira_payload, follow=True)
        jira_profile = ProviderProfileConfig.objects.get(profile_id='monkey-jira-profile')
        self.assertEqual(200, save_profile_response.status_code)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_ENABLED, jira_profile.lifecycle_state)

        hsdes_payload = self._hsdes_profile_payload('monkey-hsdes-profile')
        with patch('bug_metrics.app.api.provider_profile_connection_test.HsdesHttpClient') as hsdes_client:
            hsdes_client.return_value.execute_saved_query.return_value = {'total': 1, 'data': [{'id': '1'}]}
            hsdes_response = self.client.post(reverse('ui_web:provider_setup'), {
                **hsdes_payload,
                'action': 'test_connection',
            })
        hsdes_content = hsdes_response.content.decode()
        self.assertEqual(200, hsdes_response.status_code)
        self.assertIn('HSD-ES Connection Probe', hsdes_content)
        self.assertIn('value="15017652869"', hsdes_content)
        self.assertIn('value="ip_fw_sw_sensing.tenant"', hsdes_content)
        self.assertIn('value="ip_fw_sw_sensing.bug"', hsdes_content)
        self.assertIn('HSD-ES saved-query probe succeeded.', hsdes_content)
        self.assertNotIn('Advanced source settings', hsdes_content)

        self.client.post(reverse('ui_web:provider_setup'), hsdes_payload, follow=True)
        self.assertEqual(
            ProviderProfileConfig.LIFECYCLE_ENABLED,
            ProviderProfileConfig.objects.get(profile_id='monkey-hsdes-profile').lifecycle_state,
        )

        hsdes_scope_page = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'hsdes',
            'profile_id': 'monkey-hsdes-profile',
        })
        hsdes_scope_content = hsdes_scope_page.content.decode()
        self.assertEqual(200, hsdes_scope_page.status_code)
        self.assertIn('option value="monkey-hsdes-profile" selected', hsdes_scope_content)
        self.assertIn('scope-provider-choice is-provider-blue is-selected', hsdes_scope_content)

        scope_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'jira',
            'profile_id': 'monkey-jira-profile',
        })
        scope_content = scope_response.content.decode()
        self.assertEqual(200, scope_response.status_code)
        self.assertIn('option value="monkey-jira-profile" selected', scope_content)
        self.assertIn('scope-provider-choice is-provider-green is-selected', scope_content)
        scope_required_state = self._measure_required_submit(
            scope_content,
            'button[name="action"][value="save_enable"]',
        )
        self.assertIn('critical_high_values', scope_required_state['invalid_field_names'])
        self.assertIn('open_status_values', scope_required_state['invalid_field_names'])
        self.assertEqual(
            len(scope_required_state['invalid_field_names']),
            scope_required_state['invalid_aria_count'],
        )
        self.assertGreater(scope_required_state['missing_shell_count'], 0)
        self.assertTrue(scope_required_state['summary_visible'])

        save_scope_response = self.client.post(
            reverse('ui_web:bug_trend_scope_config'),
            self._scope_payload('Monkey Jira Scope', 'monkey-jira-profile'),
            follow=True,
        )
        scope = JiraScopeConfig.objects.get(name='Monkey Jira Scope')
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(200, save_scope_response.status_code)
        self.assertTrue(scope.enabled)
        self.assertEqual('monkey-jira-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)

        run, bucket = self._seed_run_and_issue(scope)
        workbench_response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-09-01',
            'end': '2026-09-07',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })
        workbench_content = workbench_response.content.decode()
        self.assertEqual(200, workbench_response.status_code)
        self.assertIn('id="workbench-profile" value="monkey-jira-profile"', workbench_content)
        self.assertIn('id="workbench-provider" value="jira"', workbench_content)
        self.assertIn('MONKEY-1', workbench_content)
        self.assertIn('data-workbench-evidence-workspace', workbench_content)
