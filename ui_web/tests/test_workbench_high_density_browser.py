from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
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
        self.assertEqual('2 selected', result['selected_count'])
        self.assertEqual(2, result['selected_ticket_payload']['selectedTicketCount'])
        self.assertFalse(result['selected_ticket_payload']['truncated'])
        self.assertEqual(['STDEL-9201', 'STDEL-9202'], [ticket['issueKey'] for ticket in result['selected_ticket_payload']['tickets']])
        self.assertNotIn('sourceUrl', result['selected_ticket_payload']['tickets'][0])
        self.assertEqual('2 selected tickets', result['bulk_detail_issue'])
        self.assertTrue(result['status_column_hidden'])
        self.assertEqual('STDEL-9202', result['first_issue_after_sort'])
        self.assertTrue(result['chart_collapsed'])
        self.assertNotEqual('3.15rem', result['chart_height'])
        self.assertTrue(result['detail_collapsed_after_close'])
        self.assertTrue(result['ai_collapsed'])
        self.assertNotEqual('44px', result['ai_width'])

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

        # When
        result = self._exercise_workbench_scope_sync_and_sidebar_resize(response, hsdes_scope.id)

        # Then
        self.assertGreater(int(result['resized_sidebar_width'].removesuffix('px')), int(result['initial_sidebar_width'].removesuffix('px')))
        self.assertEqual(result['resized_sidebar_width'], result['stored_sidebar_width'])
        self.assertEqual('nvu-ttl-hsdes', result['profile_value'])
        self.assertEqual('hsdes', result['provider_value'])

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
        return scope, run, bucket
