from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.app.api import bug_trend_api
from bug_metrics.app.api.chart_catalog import AiChartDraftRequest
from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, BugTrendChartDefinition, BugTrendEvidenceContract, JiraScopeConfig


class TestBugTrendChartSelectorViews(TestCase):
    def test_shouldNotReturnSelectedSeriesOutsideSelectedCatalogChartSpec(self):
        # Given
        scope, run, bucket = self._seed_open_and_fixed_memberships()
        draft = bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
            chart_id='ai_open_selected_only',
            title='AI Open Selected Only',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract_id='default_bug_trend_bucket_series',
            spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'series': ['all_open_bugs']},
        ))
        bug_trend_api.publish_chart(draft.chart_id)

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'ai_open_selected_only',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual([], payload['rows'])
        self.assertEqual(0, payload['total_count'])

    def test_shouldRenderUnsupportedEvidenceStateForSummaryOnlySelectedChart(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL summary selector',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 8, 1),
            source_coverage_end=date(2026, 8, 31),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        self._publish_summary_only_chart()

        # When
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'summary_only_chart',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Summary-only chart has no ticket evidence.', content)
        self.assertNotIn('Evidence tickets for visible range', content)

    def test_shouldNotFallbackToDefaultSeriesForSummaryOnlySelectedChart(self):
        # Given
        scope, run, bucket = self._seed_open_and_fixed_memberships()
        bucket.open_count = 1
        bucket.fixed_or_closed_count = 1
        bucket.save()
        self._publish_summary_only_chart()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'summary_only_chart',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual([], payload['datasets'])
        self.assertEqual([], payload['points'])

    def _seed_open_and_fixed_memberships(self):
        scope = JiraScopeConfig.objects.create(
            name='STDEL selected series',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 8, 1),
            source_coverage_end=date(2026, 8, 31),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        BugTrendBucketIssue.objects.create(scope=scope, bucket=bucket, calculation_run=run, series_name='all_open_bugs', issue_key='STDEL-1')
        BugTrendBucketIssue.objects.create(scope=scope, bucket=bucket, calculation_run=run, series_name='fixed_or_closed_bugs', issue_key='STDEL-2')
        return scope, run, bucket

    def _publish_summary_only_chart(self):
        contract = BugTrendEvidenceContract.objects.create(
            contract_id='summary_selector_contract',
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