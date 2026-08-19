from datetime import date, datetime, timezone

from django.test import TestCase

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters, bug_trend_api
from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig


class TestBugTrendPageQueryState(TestCase):
    def test_shouldReturnVisibleRangeEvidenceFromSameChartRun(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        bucket = self._create_bucket(scope, run, date(2026, 8, 3), date(2026, 8, 9), open_count=2)
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-1001', owner='Alice')
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-1002', owner='Bob')

        # When
        result = bug_trend_api.get_evidence_tickets(
            BugTrendPageQueryState(scope.id, date(2026, 8, 3), date(2026, 8, 9), calculation_run_id=str(run.id))
        )

        # Then
        self.assertEqual(2, result.total_count)
        self.assertEqual(2, result.shown_count)
        self.assertEqual('Evidence tickets for visible range', result.selection_title)
        self.assertEqual(['STDEL-1001', 'STDEL-1002'], [row.issue_key for row in result.rows])

    def test_shouldReturnDistinctTicketsForVisibleRangeEvidence(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        bucket = self._create_bucket(scope, run, date(2026, 8, 3), date(2026, 8, 9), open_count=1, fixed_or_closed_count=1)
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-1101', owner='Alice')
        self._create_membership(scope, run, bucket, 'fixed_or_closed_bugs', 'STDEL-1101', owner='Alice')

        # When
        result = bug_trend_api.get_evidence_tickets(
            BugTrendPageQueryState(scope.id, date(2026, 8, 3), date(2026, 8, 9), calculation_run_id=str(run.id))
        )

        # Then
        self.assertEqual(1, result.total_count)
        self.assertEqual(1, result.shown_count)
        self.assertEqual(['STDEL-1101'], [row.issue_key for row in result.rows])
        self.assertEqual('all_open_bugs, fixed_or_closed_bugs', result.rows[0].series_name)

    def test_shouldReturnBucketSeriesEvidenceWithPositiveCountForNegativeChartSeries(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        bucket = self._create_bucket(scope, run, date(2026, 8, 3), date(2026, 8, 9), fixed_or_closed_count=1)
        self._create_membership(scope, run, bucket, 'fixed_or_closed_bugs', 'STDEL-2001', status='Fixed')

        # When
        result = bug_trend_api.get_evidence_tickets(
            BugTrendPageQueryState(
                scope.id,
                date(2026, 8, 3),
                date(2026, 8, 9),
                calculation_run_id=str(run.id),
                selected_bucket_id=str(bucket.id),
                selected_series_name='fixed_or_closed_bugs',
            )
        )

        # Then
        self.assertEqual(1, result.total_count)
        self.assertEqual(1, result.shown_count)
        self.assertEqual('fixed_or_closed_bugs tickets for 26WW32', result.selection_title)
        self.assertEqual(['STDEL-2001'], [row.issue_key for row in result.rows])

    def test_shouldReportShownOfTotalWhenListLocalFilterNarrowsEvidence(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        bucket = self._create_bucket(scope, run, date(2026, 8, 3), date(2026, 8, 9), open_count=2)
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-3001', owner='Alice')
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-3002', owner='Bob')

        # When
        result = bug_trend_api.get_evidence_tickets(
            BugTrendPageQueryState(
                scope.id,
                date(2026, 8, 3),
                date(2026, 8, 9),
                calculation_run_id=str(run.id),
                list_filters=BugTrendTicketListFilters(owner='Alice'),
            )
        )

        # Then
        self.assertEqual(2, result.total_count)
        self.assertEqual(1, result.shown_count)
        self.assertEqual(['STDEL-3001'], [row.issue_key for row in result.rows])

    def test_shouldValidateChartListSyncBeforeListLocalFilters(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        bucket = self._create_bucket(scope, run, date(2026, 8, 3), date(2026, 8, 9), open_count=2)
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-4001', owner='Alice')
        self._create_membership(scope, run, bucket, 'all_open_bugs', 'STDEL-4002', owner='Bob')

        # When
        sync_result = bug_trend_api.validate_chart_list_sync(
            BugTrendPageQueryState(
                scope.id,
                date(2026, 8, 3),
                date(2026, 8, 9),
                calculation_run_id=str(run.id),
                list_filters=BugTrendTicketListFilters(owner='Alice'),
            )
        )

        # Then
        self.assertTrue(sync_result.is_consistent)
        self.assertEqual([], sync_result.mismatches)

    def test_shouldValidateChartScopeEvenWhenBucketSeriesIsSelected(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        first_bucket = self._create_bucket(scope, run, date(2026, 8, 3), date(2026, 8, 9), open_count=1)
        second_bucket = self._create_bucket(scope, run, date(2026, 8, 10), date(2026, 8, 16), open_count=1)
        self._create_membership(scope, run, first_bucket, 'all_open_bugs', 'STDEL-4101')
        self._create_membership(scope, run, second_bucket, 'all_open_bugs', 'STDEL-4102')

        # When
        sync_result = bug_trend_api.validate_chart_list_sync(
            BugTrendPageQueryState(
                scope.id,
                date(2026, 8, 3),
                date(2026, 8, 16),
                calculation_run_id=str(run.id),
                selected_bucket_id=str(first_bucket.id),
                selected_series_name='all_open_bugs',
            )
        )

        # Then
        self.assertTrue(sync_result.is_consistent)
        self.assertEqual([], sync_result.mismatches)

    def test_shouldKeepEvidencePinnedToChartRunWhenNewerRunExists(self):
        # Given
        scope = self._create_scope()
        chart_run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        chart_bucket = self._create_bucket(scope, chart_run, date(2026, 8, 3), date(2026, 8, 9), open_count=1)
        self._create_membership(scope, chart_run, chart_bucket, 'all_open_bugs', 'STDEL-5001')
        newer_run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31))
        newer_bucket = self._create_bucket(scope, newer_run, date(2026, 8, 3), date(2026, 8, 9), open_count=1)
        self._create_membership(scope, newer_run, newer_bucket, 'all_open_bugs', 'STDEL-5002')

        # When
        result = bug_trend_api.get_evidence_tickets(
            BugTrendPageQueryState(
                scope.id,
                date(2026, 8, 3),
                date(2026, 8, 9),
                calculation_run_id=str(chart_run.id),
                selected_bucket_id=str(chart_bucket.id),
                selected_series_name='all_open_bugs',
            )
        )

        # Then
        self.assertEqual(['STDEL-5001'], [row.issue_key for row in result.rows])

    def _create_scope(self):
        return JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
        )

    def _create_run(self, scope, coverage_start, coverage_end):
        return BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=coverage_start,
            source_coverage_end=coverage_end,
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

    def _create_bucket(self, scope, run, bucket_start, bucket_end, open_count=0, fixed_or_closed_count=0):
        return BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            open_count=open_count,
            fixed_or_closed_count=fixed_or_closed_count,
        )

    def _create_membership(self, scope, run, bucket, series_name, issue_key, status='Open', owner='Alice'):
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
            component_value='emulation',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )