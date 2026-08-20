from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue


class TestBugTrendViews(TestCase):
    def test_shouldRenderDashboardWithSavedScopeAndChartPayload(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('Bug Trend Indicator', content)
        self.assertIn(str(run.id), content)
        self.assertIn(str(bucket.id), content)
        self.assertIn('bugTrendChart', content)
        self.assertIn('Freshness: fresh', content)
        self.assertIn('Run config hash:', content)
        self.assertIn(scope.config_version_hash, content)
        self.assertIn('Coverage: 2026-08-03 to 2026-08-09', content)
        self.assertIn('Completed: 2026-08-19T00:00:00+00:00', content)

    def test_shouldShowStaleRunGuidanceWhenScopeConfigChanged(self):
        # Given
        scope, run, _ = self._seed_trend_data()
        old_hash = scope.config_version_hash
        scope.fixed_status_values = ['Fixed', 'Verified Fixed']
        scope.save()

        # When
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn(str(run.id), content)
        self.assertIn('Freshness: stale_config', content)
        self.assertIn(old_hash, content)
        self.assertIn(scope.config_version_hash, content)
        self.assertIn('Recalculate this scope before using this chart as current evidence.', content)
        self.assertNotIn('id="bug-trend-evidence-container"', content)

    def test_shouldNotRenderEvidencePanelWhenSelectedRangeHasNoRun(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL empty trend',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('No completed calculation covers the selected range', content)
        self.assertNotIn('id="bug-trend-evidence-container"', content)
        self.assertNotIn('Evidence tickets for visible range', content)

    def test_shouldRenderEvidenceForRequestedRunAndBucket(self):
        # Given
        _, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': bucket.scope_id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('STDEL-8942', content)
        self.assertIn('fixed_or_closed_bugs tickets for 26WW32', content)

    def test_shouldNotRenderStaleEvidenceForDirectPartialRequest(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        scope.fixed_status_values = ['Fixed', 'Verified Fixed']
        scope.save()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('0 of 0 evidence tickets shown', content)
        self.assertNotIn('STDEL-8942', content)

    def _seed_trend_data(self):
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            display_fields=['customfield_bug_type'],
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
            fixed_or_closed_count=1,
            open_count=1,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-8942',
            summary='Failure in emulation flow',
            issue_type='Bug',
            status='Fixed',
            severity_value='P3-Medium',
            component_value='team_emulation',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            raw_fields_json={'customfield_bug_type': {'value': 'Emulation'}},
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='fixed_or_closed_bugs',
            issue_key='STDEL-8942',
            summary='Failure in emulation flow',
            status='Fixed',
            severity_value='P3-Medium',
            component_value='team_emulation',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            extra_fields_json={'customfield_bug_type': 'Emulation'},
        )
        return scope, run, bucket