from datetime import date, datetime, timezone
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from bug_metrics.models import (
    BugTrendBucket,
    BugTrendBucketIssue,
    BugTrendCalculationRun,
    BugTrendChartDefinition,
    BugTrendEvidenceContract,
    BugTrendScopeProviderBinding,
    JiraScopeConfig,
)
from ui_web.workbench_registry import default_workbench_panes
from ui_web.tests.workbench_browser_test_support import WorkbenchBrowserTestSupport


from ui_web.tests.workbench_view_test_support import WorkbenchViewTestSupport


class TestWorkbenchViews(WorkbenchViewTestSupport, WorkbenchBrowserTestSupport, TestCase):
    def test_shouldRenderWorkbenchShellWithRegisteredPaneLandmarks(self):
        # When
        response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Metrics Workbench', content)
        self.assertIn('data-workbench-pane="chart"', content)
        self.assertIn('data-workbench-pane="evidence"', content)
        self.assertIn('data-workbench-pane="ai-assistant"', content)
        self.assertIn('data-workbench-nav-link', content)
        self.assertNotIn('data-workbench-pane="utility"', content)
        self.assertNotIn('Settings, Publish, Audit', content)
        self.assertIn('data-workbench-status-bar', content)
        self.assertIn('data-workbench-job-status', content)
        self.assertIn('workbench-status-brand', content)
        self.assertIn('No active job', content)
        self.assertIn('Dashboard UI:', content)
        self.assertIn('workbench-status-time">@', content)
        self.assertNotIn('workbench-status-url', content)
        self.assertIn('workbench-control-grid', content)
        self.assertIn('dashboard-top-toolbar workbench-toolbar', content)
        self.assertIn('workbench-toolbar-field-scope', content)
        self.assertIn('id="workbench-scope" name="scope_id" data-workbench-state-trigger="scope"', content)
        self.assertNotIn('onchange="this.form.requestSubmit()"', content)
        self.assertIn('workbench-control-input" id="workbench-profile"', content)
        self.assertIn('workbench-control-input" id="workbench-provider"', content)
        self.assertIn('workbench-control-input" id="workbench-begin"', content)
        self.assertIn('workbench-control-input" id="workbench-end"', content)
        self.assertIn('workbench-apply-button', content)
        self.assertIn('data-dashboard-sidebar-splitter', content)
        self.assertIn('data-workbench-splitter="chart-evidence"', content)
        self.assertIn('data-workbench-splitter="main-ai"', content)
        self.assertIn('data-workbench-collapse="chart"', content)
        self.assertIn('data-workbench-collapse="ai-assistant"', content)
        self.assertIn('class="help-tip"', content)
        self.assertIn('The query scope that drives the chart range', content)
        self.assertIn('Embedded AI Base chat bound to the selected scope profile', content)
        self.assertNotIn('compact panel ready', content)
        self.assertNotIn('&copy; 2017', content)

    def test_shouldRenderServiceStatusBarOnNonWorkbenchPages(self):
        # When
        with tempfile.TemporaryDirectory() as state_dir:
            with override_settings(METRICS_STATE_DIR=state_dir):
                response = self.client.get(reverse('ui_web:homepage'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('data-workbench-status-bar', content)
        self.assertIn('Dashboard UI:', content)
        self.assertIn('status-tone-success', content)
        self.assertNotIn('workbench-status-item is-success', content)

    def test_shouldRenderGlobalStatusBarWithoutAiProbeOnNonWorkbenchPages(self):
        # When
        with patch('ui_web.context_processors.ui_web_container.bug_trend_facade.get_ai_sidecar_status_payload') as status_payload:
            status_payload.side_effect = AssertionError('Non-Workbench pages should not run AI sidecar probes.')
            with tempfile.TemporaryDirectory() as state_dir:
                with override_settings(METRICS_STATE_DIR=state_dir):
                    response = self.client.get(reverse('ui_web:homepage'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('data-workbench-status-bar', content)
        status_payload.assert_not_called()

    def test_shouldRenderLifecycleStateInWorkbenchServiceStatusBar(self):
        # Given
        with tempfile.TemporaryDirectory() as state_dir:
            state_path = Path(state_dir) / 'e2e' / 'service-lifecycle-engine' / 'metrics-bug-trend-default.json'
            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps({
                'schema_version': 1,
                'services': {
                    'grafana': {
                        'pid': os.getpid(),
                        'port': 3210,
                        'host': '127.0.0.1',
                        'lifecycle_state': 'ready',
                        'started_at': '2026-09-09T00:59:35+00:00',
                        'provenance': {
                            'capability': 'endpoint_grade',
                            'wrapper_pid': os.getpid(),
                            'listener_pid': os.getpid(),
                        },
                    },
                },
            }), encoding='utf-8')

            # When
            with override_settings(METRICS_STATE_DIR=state_dir, METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:3001'):
                response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('data-service-id="grafana"', content)
        self.assertIn('data-service-status="connected"', content)
        self.assertIn('href="http://127.0.0.1:3210"', content)

    def test_shouldNotFallbackToConnectedWhenDashboardLifecycleStateIsStopped(self):
        # Given
        with tempfile.TemporaryDirectory() as state_dir:
            state_path = Path(state_dir) / 'e2e' / 'service-lifecycle-engine' / 'metrics-bug-trend-default.json'
            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps({
                'schema_version': 1,
                'services': {
                    'django': {
                        'pid': os.getpid(),
                        'port': 8012,
                        'host': '127.0.0.1',
                        'lifecycle_state': 'stopped',
                        'started_at': '2026-09-09T00:59:35+00:00',
                    },
                },
            }), encoding='utf-8')

            # When
            with override_settings(METRICS_STATE_DIR=state_dir):
                response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('data-service-id="dashboard"', content)
        self.assertIn('data-service-status="stopped"', content)

    def test_shouldFailClosedWhenWorkbenchLifecycleStateIsCorrupt(self):
        # Given
        with tempfile.TemporaryDirectory() as state_dir:
            state_path = Path(state_dir) / 'e2e' / 'service-lifecycle-engine' / 'metrics-bug-trend-default.json'
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{not-json', encoding='utf-8')

            # When
            with override_settings(METRICS_STATE_DIR=state_dir, METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:3001'):
                response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('data-service-id="grafana"', content)
        self.assertIn('data-service-status="configured"', content)

    def test_shouldExposeDefaultWorkbenchPaneRegistry(self):
        # When
        panes = list(default_workbench_panes())

        # Then
        self.assertEqual(
            ['chart', 'evidence', 'ai-assistant', 'settings', 'publish-audit', 'diagnostics'],
            [pane.pane_id for pane in panes],
        )
        for pane in panes:
            self.assertTrue(pane.title)
            self.assertTrue(pane.capability)
            self.assertTrue(pane.source_type)
            self.assertTrue(pane.target_route)
            self.assertTrue(pane.default_placement)
            self.assertIn(pane.default_placement, pane.allowed_placements)

    @override_settings(METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldRenderAiBaseUnavailableWithoutBlockingWorkbench(self):
        # When
        with tempfile.TemporaryDirectory() as state_dir:
            with override_settings(METRICS_STATE_DIR=state_dir):
                response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI Base', content)
        self.assertIn('disabled', content)
        self.assertIn('AI chat is not enabled for this Dashboard process.', content)
        self.assertIn('scripts\\e2e_dashboard_ai_stack.ps1 -Action restart -ForceByPort', content)
        self.assertIn('Dashboard UI:', content)
        self.assertIn('data-service-status="connected"', content)
        self.assertIn('Grafana', content)
        self.assertIn('configured', content)
        self.assertIn('at ', content)
        self.assertIn('workbench-ai-binding-note', content)
        self.assertIn('Scope Binding', content)

    @override_settings(METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldShowScopeBindingRepairBeforeAiWorkspaceHintWhenBindingIsMissing(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Unbound workbench AI scope',
            jql='',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('"scope_binding": {"status": "configuration_required"', content)
        self.assertIn('id="workbench-profile" value="" readonly data-workbench-derived-field="profile_id"', content)
        self.assertIn('id="workbench-provider" value="" readonly data-workbench-derived-field="provider_id"', content)
        self.assertIn('Scope is not bound to a provider profile.', content)
        self.assertIn(reverse('ui_web:bug_trend_scope_library'), content)

    @override_settings(METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldIncludeResolvedScopeBindingInAiContext(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Resolved workbench AI scope',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('"scope_binding": {"status": "explicit"', content)
        self.assertIn('"profile_id": "chiplet-2a-jira"', content)
        self.assertIn('"provider_id": "jira"', content)

    @patch('ui_web.facades.bug_trend_facade.BugTrendFacade.get_ai_sidecar_status_payload')
    def test_shouldGateAiIframeWhenScopeBindingProfileIsNotRegistryBacked(self, status_payload):
        # Given
        status_payload.return_value = {
            'enabled': True,
            'status': 'ready',
            'base_url': 'http://127.0.0.1:48300',
            'profile_id': 'dashboard_query_agent',
            'service_id': 'dashboard-query-agent-app-service',
            'capabilities': {'dashboardQuery': True, 'metricsConnector': True},
        }
        scope = JiraScopeConfig.objects.create(
            name='Legacy explicit scope',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='Legacy explicit scope',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI workspace needs a registry-backed profile.', content)
        self.assertIn('Rebind this scope in Scope Library.', content)
        self.assertNotIn('AI Base chat side window', content)

    @override_settings(METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldWarnButRenderProviderPanesForCompatibilityBinding(self):
        # Given
        scope, run, bucket = self._seed_trend_data(bind_profile=False)
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'matched_by': 'legacy_jira_scope'},
        )

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('This scope is using a compatibility provider binding.', content)
        self.assertIn(str(run.id), content)
        self.assertIn(str(bucket.id), content)
        self.assertIn('"scope_binding": {"status": "compatibility"', content)

    @override_settings(METRICS_SCOPE_BINDING_POLICY='explicit_only', METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldBlockCompatibilityBindingWhenPolicyIsExplicitOnly(self):
        # Given
        scope, run, bucket = self._seed_trend_data(bind_profile=False)
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'matched_by': 'legacy_jira_scope'},
        )

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Scope uses a compatibility binding and must be confirmed before explicit-only operation.', content)
        self.assertIn('id="workbench-profile" value="" readonly data-workbench-derived-field="profile_id"', content)
        self.assertIn('id="workbench-provider" value="" readonly data-workbench-derived-field="provider_id"', content)
        self.assertNotIn('data-workbench-evidence-workspace', content)

    def test_shouldKeepToolbarAndEvidenceFilterStateBoundariesSeparate(self):
        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'nvu-ttl-hsdes',
            'provider_id': 'hsdes',
            'range_mode': 'date',
            'begin': '2026-08-01',
            'end': '2026-08-31',
            'chart_id': 'open_bug_trend',
            'chart_version': '2',
            'run': 'run-1',
            'bucket': 'bucket-1',
            'series': 'new_critical_high',
            'text': 'display',
            'status': 'open',
            'severity': 'critical',
            'owner': 'alice',
            'component': 'media',
        })

        # Then
        content = response.content.decode()
        self.assertIn('hx-target=".workbench-shell"', content)
        self.assertIn('Selection: bucket-1 new_critical_high', content)
        self.assertIn('workbench-evidence-filter-grid', content)
        self.assertIn('dashboard-tool-field', content)
        self.assertNotIn('columns is-variable is-2', content)
        self.assertNotIn('field has-addons', content)
        self.assertIn('name="scope_id" value="', content)
        self.assertIn('name="text" value="display"', content)
        self.assertIn('name="status" value="open"', content)
        self.assertIn('name="severity" value="critical"', content)
        self.assertIn('name="owner" value="alice"', content)
        self.assertIn('name="component" value="media"', content)

    def test_shouldNormalizeDefaultScopeIntoWorkbenchStateForLinkedFilters(self):
        # Given
        scope, _, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn(f'name="scope_id" value="{scope.id}"', content)
        self.assertIn(f'var-scope_id={scope.id}', content)

    def test_shouldResolveProviderFromProfileAndKeepProviderReadOnly(self):
        # Given
        scope = self._bound_scope('chiplet-2a-jira', 'jira')

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'range_mode': 'ww',
            'begin': '2026-06-01',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('id="workbench-provider" value="jira" readonly data-workbench-derived-field="provider_id"', content)
        self.assertIn('providerId=jira', content)
        self.assertIn('sourceAppId=metrics-dashboard', content)

    def test_shouldShowValidationFailureForInvalidSelectionWithoutStaleRows(self):
        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'nvu-ttl-hsdes',
            'chart_id': 'open_bug_trend',
            'bucket': 'bucket-1',
            'series': 'new_critical_high',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Chart evidence selection requires a calculation run or fact snapshot.', content)
        self.assertIn('Evidence pane placeholder', content)
