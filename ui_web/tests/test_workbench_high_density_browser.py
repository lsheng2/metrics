from datetime import date, datetime, timezone

from django.test import TestCase, override_settings
from django.urls import reverse

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, BugTrendScopeProviderBinding, JiraScopeConfig
from ui_web.tests import ui_geometry_contract as geometry
from ui_web.tests.workbench_browser_test_support import WorkbenchBrowserTestSupport


class TestWorkbenchHighDensityBrowser(WorkbenchBrowserTestSupport, TestCase):
    def test_shouldSupportHighDensityWorkbenchInteractionsInBrowser(self):
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
            owner_value='Bob',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='STDEL-9202',
            summary='Critical validation failure',
            status='Review',
            severity_value='P1-Critical',
            component_value='validation',
            owner_value='Alice',
            created_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        )
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })

        # When
        result = self._exercise_workbench_high_density_interactions(response)

        # Then
        self.assertTrue(result['initial_detail_collapsed'])
        self.assertTrue(result['detail_open'])
        self.assertEqual('STDEL-9201', result['detail_issue'])
        self.assertEqual('2026-08-04 00:00 UTC', result['detail_created'])
        self.assertEqual('261px', result['ticket_detail_width'])
        self.assertEqual({'now': '261', 'min': '180', 'max': '360'}, result['ticket_splitter_aria'])
        self.assertEqual('2 selected', result['selected_count'])
        self.assertEqual(2, result['selected_ticket_payload']['selectedTicketCount'])
        self.assertFalse(result['selected_ticket_payload']['truncated'])
        self.assertEqual(['STDEL-9201', 'STDEL-9202'], [ticket['issueKey'] for ticket in result['selected_ticket_payload']['tickets']])
        self.assertNotIn('sourceUrl', result['selected_ticket_payload']['tickets'][0])
        self.assertEqual('2 selected tickets', result['bulk_detail_issue'])
        self.assertTrue(result['status_column_hidden'])
        self.assertFalse(result['columns_menu_open_after_blank_click'])
        self.assertEqual('STDEL-9202', result['first_issue_after_sort'])
        self.assertTrue(result['chart_collapsed'])
        self.assertNotEqual('3.15rem', result['chart_height'])
        self.assertEqual('50', result['chart_splitter_aria']['min'])
        self.assertEqual(result['chart_height'].removesuffix('px'), result['chart_splitter_aria']['now'])
        self.assertTrue(result['detail_collapsed_after_close'])
        self.assertTrue(result['ai_collapsed'])
        self.assertEqual('AI', result['ai_button_text'])
        self.assertFalse(result['ai_title_visible'])
        self.assertNotEqual('44px', result['ai_width'])
        self.assertGreaterEqual(int(result['ai_width'].removesuffix('px')), geometry.WORKBENCH_AI_PANE_MIN_WIDTH)
        self.assertEqual({'now': result['ai_width'].removesuffix('px'), 'min': '40', 'max': '600'}, result['ai_splitter_aria'])
        self.assertLessEqual(abs(result['layout_metrics']['appTop']), geometry.ALIGNMENT_TOLERANCE)
        self.assertLessEqual(abs(result['layout_metrics']['sidebarTop']), geometry.ALIGNMENT_TOLERANCE)
        self.assertLessEqual(result['layout_metrics']['shellTop'], geometry.WORKBENCH_SHELL_TOP_MAX)
        self.assertLessEqual(result['layout_metrics']['shellRightGap'], geometry.ALIGNMENT_TOLERANCE)
        self.assertLessEqual(result['layout_metrics']['aiRightGap'], geometry.ALIGNMENT_TOLERANCE)
        self.assertLessEqual(result['layout_metrics']['aiWidth'], geometry.WORKBENCH_COLLAPSED_AI_WIDTH_MAX)
        self.assertEqual('40px', result['layout_metrics']['aiWidthVar'])
        self.assertLessEqual(abs(result['layout_metrics']['statusBottomGap']), geometry.ALIGNMENT_TOLERANCE)
        self.assertGreaterEqual(result['layout_metrics']['statusHeight'], geometry.WORKBENCH_STATUS_BAR_MIN_HEIGHT)
        self.assertEqual(0, result['layout_metrics']['toolbarLabelClippingCount'])
        self.assertGreaterEqual(result['layout_metrics']['toolbarMinLabelTopGap'], geometry.WORKBENCH_TOOLBAR_LABEL_TOP_GAP_MIN)
        self.assertTrue(result['restored_ai_collapsed'])
        self.assertEqual('AI', result['restored_ai_button_text'])
        self.assertFalse(result['restored_ai_title_visible'])

    def test_shouldStackWorkbenchPanesIntoAScrollablePageOnPhones(self):
        # Given
        response = self._get_selected_bucket_workbench('STDEL-9401', 'STDEL-9402', 'STDEL-9403')

        # When
        result = self._exercise_workbench_phone_layout(response)

        # Then
        self.assertFalse(result['scroll_locked'])
        self.assertNotEqual('none', result['topbar_display'])
        self.assertEqual(['chart', 'evidence', 'ai-assistant'], result['pane_order'])
        self.assertLessEqual(result['pane_width_delta'], geometry.ALIGNMENT_TOLERANCE)
        self.assertLessEqual(result['gutter_delta'], geometry.ALIGNMENT_TOLERANCE)
        self.assertGreaterEqual(result['chart_frame_height'], geometry.WORKBENCH_PHONE_CHART_MIN_HEIGHT)
        self.assertLessEqual(result['pane_header_overlap'], geometry.OVERFLOW_TOLERANCE)
        self.assertEqual([1, 1, 1], result['pane_title_lines'])
        self.assertEqual(['none', 'none', 'none'], result['splitter_displays'])
        self.assertEqual(1, result['evidence_columns'])
        self.assertGreaterEqual(result['detail_gap_below_table'], 0)
        self.assertLessEqual(result['detail_under_topbar'], geometry.OVERFLOW_TOLERANCE)
        self.assertLessEqual(result['detail_under_status_bar'], geometry.OVERFLOW_TOLERANCE)
        self.assertLessEqual(result['ai_under_status_bar'], geometry.OVERFLOW_TOLERANCE)
        self.assertLessEqual(result['collapsed_ai_width_delta'], geometry.ALIGNMENT_TOLERANCE)
        self.assertEqual('none', result['collapsed_ai_body_display'])
        self.assertTrue(result['collapsed_ai_title_visible'])
        self.assertEqual('Expand', result['collapsed_ai_button_text'])

    def test_shouldSyncScopeBoundProfileAndResizeGlobalSidebarInBrowser(self):
        # Given
        JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        hsdes_scope = JiraScopeConfig.objects.create(
            name='nvu-ttl-hsdes',
            jql='project = NVU AND type = bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['critical'],
            medium_low_values=['medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        response = self.client.get(reverse('ui_web:workbench'), {
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })
        target_response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': hsdes_scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # When
        result = self._exercise_workbench_scope_sync_and_sidebar_resize(response, hsdes_scope.id, target_response)

        # Then
        self.assertGreater(int(result['resized_sidebar_width'].removesuffix('px')), int(result['initial_sidebar_width'].removesuffix('px')))
        self.assertEqual(result['resized_sidebar_width'], result['stored_sidebar_width'])
        self.assertIn(f'scope_id={hsdes_scope.id}', result['htmx_url'])
        self.assertNotIn('profile_id=', result['htmx_url'])
        self.assertNotIn('provider_id=', result['htmx_url'])
        self.assertEqual('nvu-ttl-hsdes', result['profile_value'])
        self.assertEqual('hsdes', result['provider_value'])

    @override_settings(METRICS_AI_SIDECAR_ENABLED=False)
    def test_shouldKeepWorkbenchUsableInStandaloneModeWhenAiIsDisabled(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='STDEL-9301',
            summary='Critical standalone issue',
            status='Open',
            severity_value='P1-Critical',
            component_value='media',
            owner_value='Bob',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })

        # When
        result = self._exercise_workbench_standalone_ai_disabled(response)

        # Then
        self.assertTrue(result['chart_visible'])
        self.assertTrue(result['evidence_visible'])
        self.assertTrue(result['ai_diagnostic_visible'])
        self.assertEqual(0, result['iframe_count'])
        self.assertTrue(result['ai_collapsed'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldLoadGrafanaPreviewOnlyWhenOpenedAndFollowDashboardTheme(self):
        # Given
        scope, _run, _bucket = self._seed_trend_data()
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # When
        result = self._exercise_grafana_preview_theme(response)

        # Then
        self.assertIsNone(result['src_before_open'])
        self.assertTrue(result['src_after_open'].startswith('http://grafana.test/d-solo/metrics-bug-trend-c-stock/'))
        self.assertEqual(('light', 'dark'), (result['theme_after_open'], result['theme_after_switch']))

    def _get_selected_bucket_workbench(self, *issue_keys):
        scope, run, bucket = self._seed_trend_data()
        for day, issue_key in enumerate(issue_keys, start=4):
            BugTrendBucketIssue.objects.create(
                scope=scope,
                bucket=bucket,
                calculation_run=run,
                series_name='new_critical_high',
                issue_key=issue_key,
                summary=f'Critical issue {issue_key}',
                status='Open',
                severity_value='P1-Critical',
                component_value='media',
                owner_value='Bob',
                created_at=datetime(2026, 8, day, tzinfo=timezone.utc),
                updated_at=datetime(2026, 8, day, tzinfo=timezone.utc),
            )
        return self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })

    def _seed_trend_data(self):
        scope = JiraScopeConfig.objects.create(
            name='Workbench high density',
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
            new_critical_high_count=2,
            open_count=2,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        return scope, run, bucket
