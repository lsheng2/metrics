from datetime import date, datetime, timezone

from django.test import TestCase, override_settings
from django.urls import reverse

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig


class TestBugTrendFactTableUi(TestCase):
    @override_settings(METRICS_JIRA_SERVER_URL='https://jira.devtools.intel.com')
    def test_shouldRenderEvidenceListBelowChartForVisibleRange(self):
        # Given
        scope, _, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('Evidence tickets for visible range', content)
        self.assertIn('2 of 2 evidence tickets shown', content)
        self.assertIn('STDEL-1001', content)
        self.assertIn('https://jira.devtools.intel.com/browse/STDEL-1001', content)
        self.assertIn('STDEL-1002', content)

    def test_shouldRenderBucketSeriesEvidenceFromChartSelection(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('fixed_or_closed_bugs tickets for 26WW32', content)
        self.assertIn('1 of 1 evidence tickets shown', content)
        self.assertIn('Clear selection', content)
        self.assertIn('STDEL-1002', content)
        self.assertNotIn('STDEL-1001', content)

    def test_shouldShowDisplayedCountWhenListLocalFilterNarrowsEvidence(self):
        # Given
        scope, run, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'owner': 'Alice',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('1 of 2 evidence tickets shown', content)
        self.assertIn('STDEL-1001', content)
        self.assertNotIn('STDEL-1002', content)

    def test_shouldKeepConfiguredDisplayColumnsWhenFilterShowsNoEvidenceRows(self):
        # Given
        scope, run, _ = self._seed_trend_data(display_fields=['customfield_bug_type'])

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'owner': 'Nobody',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('customfield_bug_type', content)
        self.assertIn('0 of 2 evidence tickets shown', content)

    def test_shouldRenderConfiguredDisplayColumnsInScopeOrder(self):
        # Given
        scope, run, bucket = self._seed_trend_data(display_fields=['field_a', 'field_b'])
        membership = BugTrendBucketIssue.objects.get(scope=scope, bucket=bucket, issue_key='STDEL-1001')
        membership.extra_fields_json = {'field_b': 'B value', 'field_a': 'A value'}
        membership.save()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'all_open_bugs',
        })

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertLess(content.index('field_a'), content.index('field_b'))
        self.assertLess(content.index('A value'), content.index('B value'))

    def _seed_trend_data(self, display_fields=None):
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
            display_fields=display_fields or [],
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
            open_count=2,
        )
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-1001', 'Open', 'Alice')
        self._create_membership(scope, run, bucket, 'fixed_or_closed_bugs', 'STDEL-1002', 'Fixed', 'Bob')
        return scope, run, bucket

    def _create_membership(self, scope, run, bucket, series_name, issue_key, status, owner):
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name=series_name,
            issue_key=issue_key,
            summary=f'{issue_key} summary',
            status=status,
            severity_value='P3-Medium',
            owner_value=owner,
            component_value='team_emulation',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )