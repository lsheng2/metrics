from datetime import date, datetime, timezone
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
    JiraScopeConfig,
)
from ui_web.workbench_registry import default_workbench_panes
from ui_web.tests.workbench_browser_test_support import WorkbenchBrowserTestSupport


class TestWorkbenchViews(WorkbenchBrowserTestSupport, TestCase):
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
        self.assertIn('workbench-control-grid', content)
        self.assertIn('data-dashboard-sidebar-splitter', content)
        self.assertIn('data-workbench-splitter="chart-evidence"', content)
        self.assertIn('data-workbench-splitter="main-ai"', content)
        self.assertIn('data-workbench-collapse="chart"', content)
        self.assertIn('data-workbench-collapse="ai-assistant"', content)
        self.assertNotIn('compact panel ready', content)
        self.assertNotIn('&copy; 2017', content)

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
        response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI Base', content)
        self.assertIn('disabled', content)
        self.assertIn('AI chat is not enabled for this Dashboard process.', content)
        self.assertIn('scripts\\e2e_dashboard_ai_stack.ps1 -Action restart -ForceByPort', content)
        self.assertIn('Dashboard', content)
        self.assertIn('available', content)
        self.assertIn('Grafana', content)
        self.assertIn('configured', content)
        self.assertIn('at ', content)

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
        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'chiplet-2a-jira',
            'provider_id': '',
            'range_mode': 'ww',
            'begin': '2026-06-01',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('id="workbench-provider" name="provider_id" value="jira" readonly', content)
        self.assertIn('provider_id=jira', content)

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

    def test_shouldRenderReferenceBugTrendChartFromWorkbenchState(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

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
        self.assertIn('bugTrendChart', content)
        self.assertIn(str(run.id), content)
        self.assertIn(str(bucket.id), content)
        self.assertNotIn('Active chart: default_bug_trend', content)

    def test_shouldRenderEvidenceRowsForSelectedReferenceChartBucket(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='STDEL-9201',
            summary='Critical media crash',
            status='Open',
            severity_value='P1-Critical',
            component_value='media',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
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
        self.assertIn('STDEL-9201', content)
        self.assertIn('new_critical_high tickets for 26WW32', content)
        self.assertIn('data-workbench-evidence-workspace', content)
        self.assertIn('data-workbench-column-toggle="status"', content)
        self.assertIn('data-workbench-evidence-sort-field', content)
        self.assertIn('data-workbench-ticket-select-all', content)
        self.assertIn('data-workbench-ticket-checkbox', content)
        self.assertIn('data-workbench-ticket-detail', content)
        self.assertIn('data-workbench-splitter="ticket-detail"', content)
        self.assertIn('Open Source', content)

    def test_shouldExposeClearSelectionUrlWithoutBucketOrSeries(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
            'status': 'Open',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Clear selection', content)
        clear_link_start = content.index('<a class="button is-small"')
        clear_link_end = content.index('>Clear selection</a>', clear_link_start)
        clear_link = content[clear_link_start:clear_link_end]
        self.assertIn('run=', clear_link)
        self.assertIn('status=Open', clear_link)
        self.assertNotIn('bucket=', clear_link)
        self.assertNotIn('series=', clear_link)

    def test_shouldShowSummaryOnlyEvidenceStateWithoutStaleRows(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        self._publish_summary_only_chart()
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='STDEL-9201',
            summary='Critical media crash',
            status='Open',
            severity_value='P1-Critical',
            component_value='media',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'summary_only_chart',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('summary_only', content)
        self.assertIn('Summary-only chart has no ticket evidence.', content)
        self.assertNotIn('STDEL-9201', content)

    def test_shouldRenderCompactGrafanaPanelPreviewAndFullDashboardLink(self):
        # Given
        scope, _, _ = self._seed_trend_data()

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
        self.assertIn('/d-solo/metrics-bug-trend-c-stock/', content)
        self.assertIn('panelId=1', content)
        self.assertIn('Grafana panel preview', content)
        self.assertIn('Open full Grafana dashboard', content)

    def test_shouldExposeGrafanaSelectionBridgePage(self):
        # When
        response = self.client.get(reverse('ui_web:workbench_grafana_selection'), {
            'scope_id': '1',
            'run': 'run-1',
            'bucket': 'bucket-1',
            'series': 'new_critical_high',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('metrics-workbench:grafana-selection', content)
        self.assertIn('postMessage', content)
        self.assertIn("params.get('begin_ww')", content)
        self.assertIn("params.get('fact_snapshot_id')", content)

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='', METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldShowScopedNextActionsWhenDependentServicesAreUnavailable(self):
        # When
        response = self.client.get(reverse('ui_web:workbench'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Grafana', content)
        self.assertIn('unavailable', content)
        self.assertIn('Set METRICS_AI_GRAFANA_BASE_URL and start the Grafana service', content)
        self.assertIn('AI chat is not enabled for this Dashboard process.', content)
        self.assertIn('scripts\\e2e_dashboard_ai_stack.ps1 -Action restart -ForceByPort', content)

    def test_shouldKeepLegacyFullPageUrlsReachableFromWorkbenchNavigation(self):
        # When
        urls = [
            reverse('ui_web:bug_trend'),
            reverse('ui_web:ai_dashboard_workflow'),
            reverse('ui_web:data_health'),
        ]
        responses = [self.client.get(url) for url in urls]

        # Then
        self.assertEqual([200, 200, 200], [response.status_code for response in responses])

    def test_shouldRefreshWorkbenchFromGrafanaSelectionMessageWithoutLeavingShell(self):
        # Given
        main_js = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
        html = f"""
            <html>
            <body>
                <div id="workbench-grid"></div>
                <script>
                    window.htmx = {{
                        ajax: function(method, url, options) {{
                            window.lastHtmxCall = {{ method: method, url: url, target: options.target, select: options.select }};
                        }}
                    }};
                </script>
                <script>{main_js}</script>
            </body>
            </html>
        """

        # When
        url, location_after_message, htmx_target = self._post_grafana_selection_message(html)

        # Then
        self.assertIn('/workbench/?', url)
        self.assertIn('bucket=bucket-1', url)
        self.assertIn('series=new_critical_high', url)
        self.assertIn('run=run-1', url)
        self.assertEqual('.workbench-shell', htmx_target)
        self.assertIn('/workbench/?', location_after_message)

    @override_settings(
        METRICS_AI_SIDECAR_ENABLED=False,
        METRICS_AI_BASE_INSTANCE_TOKEN='secret-token',
        METRICS_AI_BASE_URL='http://127.0.0.1:48300',
    )
    def test_shouldExposeSafeAiPaneContextWithoutSecrets(self):
        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'nvu-ttl-hsdes',
            'provider_id': 'hsdes',
            'range_mode': 'ww',
            'begin': '26WW32',
            'end': '26WW35',
            'chart_id': 'open_bug_trend',
            'run': 'run-1',
            'bucket': 'bucket-1',
            'series': 'new_critical_high',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('workbench-ai-context', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('new_critical_high', content)
        self.assertIn('Diagnostics', content)
        self.assertIn('AI chat is not enabled for this Dashboard process.', content)
        self.assertNotIn('secret-token', content)

    @patch('ui_web.facades.bug_trend_facade.BugTrendFacade.get_ai_sidecar_status_payload')
    def test_shouldRenderReadyAiBasePaneWithCurrentContext(self, status_payload):
        # Given
        status_payload.return_value = {
            'status': 'ready',
            'profile_id': 'dashboard_query_agent',
            'service_id': 'dashboard-query-agent-app-service',
            'capabilities': {'dashboardQuery': True, 'metricsConnector': True},
        }

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'nvu-ttl-hsdes',
            'range_mode': 'ww',
            'begin': '26WW32',
            'end': '26WW35',
            'chart_id': 'open_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI Assistant', content)
        self.assertIn('AI Base chat side window', content)
        self.assertIn('tabindex="-1"', content)
        self.assertIn('http://127.0.0.1:48310/?embed=workbench#/chat?', content)
        self.assertIn('source=metrics-workbench', content)
        self.assertIn('workspace_key=metrics.hsdes.nvu-ttl-hsdes', content)
        self.assertIn('agent_id=dashboard_query_agent', content)
        self.assertIn('ready', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('open_bug_trend', content)

    def test_shouldRefreshWorkbenchEvidenceWhenReferenceChartBarIsClicked(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='STDEL-9201',
            summary='Critical media crash',
            status='Open',
            severity_value='P1-Critical',
            component_value='media',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })
        evidence_response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
            'chart_id': 'default_bug_trend',
        })

        # When
        nonblank_pixels, evidence_text, chart_config = self._render_workbench_chart_and_click_evidence(
            response,
            evidence_response,
        )

        # Then
        self.assertTrue(nonblank_pixels)
        self.assertIn('STDEL-9201', evidence_text)
        self.assertIn('new_critical_high tickets for 26WW32', evidence_text)
        self.assertIn('run=' + str(run.id), chart_config['evidenceUrl'])
        self.assertIn('series=new_critical_high', chart_config['evidenceUrl'])

    def test_shouldKeepEvidenceExportConsistentWithWorkbenchSelection(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='STDEL-9201',
            summary='Critical media crash',
            status='Open',
            severity_value='P1-Critical',
            component_value='media',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )

        # When
        page_response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })
        export_response = self.client.get(reverse('ui_web:bug_trend_evidence_export'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })

        # Then
        page_content = page_response.content.decode()
        export_content = export_response.content.decode()
        self.assertEqual(200, page_response.status_code)
        self.assertEqual(200, export_response.status_code)
        self.assertIn('STDEL-9201', page_content)
        self.assertIn('STDEL-9201', export_content)
        self.assertIn('new_critical_high', export_content)

    def _seed_trend_data(self):
        scope = JiraScopeConfig.objects.create(
            name='Workbench trend',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 8, 3),
            source_coverage_end=date(2026, 8, 9),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            new_critical_high_count=1,
            open_count=1,
        )
        return scope, run, bucket

    def _publish_summary_only_chart(self):
        contract = BugTrendEvidenceContract.objects.create(
            contract_id='workbench_summary_only_contract',
            capability=BugTrendEvidenceContract.CAPABILITY_SUMMARY_ONLY,
            membership_source='',
            membership_key='',
            ticket_identity='none',
            dedupe_policy='none',
            time_boundary_policy='none',
            export_policy='none',
            unsupported_reason='Summary-only chart has no ticket evidence.',
        )
        BugTrendChartDefinition.objects.create(
            chart_id='summary_only_chart',
            title='Summary Only',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
            status=BugTrendChartDefinition.STATUS_PUBLISHED,
            enabled=True,
        )
