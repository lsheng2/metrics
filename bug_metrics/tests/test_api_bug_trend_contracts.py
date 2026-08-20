from datetime import date, datetime, timezone

from django.test import TestCase

from bug_metrics.app.api import BugTrendPageQueryState, bug_trend_api
from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue, JiraTransition


class TestBugTrendScopeAuthority(TestCase):
    def test_shouldChangeConfigVersionWhenScopeSemanticsChange(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
        )
        original_hash = scope.config_version_hash

        # When
        scope.critical_high_values = ['P1-Critical', 'P2-High']
        scope.save()

        # Then
        self.assertNotEqual(original_hash, scope.config_version_hash)


class TestBugTrendChartContract(TestCase):
    def test_shouldReturnChartFromMatchingCompletedRunWhenRangeIsCovered(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31), scope.config_version_hash)
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            new_critical_high_count=2,
            new_medium_low_count=3,
            fixed_or_closed_count=1,
            open_count=8,
            open_critical_high_count=4,
        )

        # When
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        self.assertEqual(str(run.id), chart.calculation_run_id)
        self.assertEqual([str(bucket.id)], chart.bucket_ids)
        self.assertEqual(['all_open_bugs', 'all_open_critical_high', 'new_critical_high', 'new_medium_low', 'fixed_or_closed_bugs'], [dataset.series_name for dataset in chart.datasets])
        self.assertEqual([8], chart.datasets[0].values)
        self.assertEqual([-1], chart.datasets[4].values)
        self.assertEqual('fresh', chart.run_metadata.freshness_status)
        self.assertEqual(str(run.id), chart.run_metadata.calculation_run_id)
        self.assertEqual(run.config_version_hash, chart.run_metadata.run_config_version_hash)
        self.assertEqual(scope.config_version_hash, chart.run_metadata.current_config_version_hash)
        self.assertEqual('2026-08-01', chart.run_metadata.source_coverage_start)
        self.assertEqual('2026-08-31', chart.run_metadata.source_coverage_end)
        self.assertEqual('2026-08-19T00:00:00+00:00', chart.run_metadata.completed_at)
        self.assertTrue(chart.current_evidence_available)

    def test_shouldRejectOldRunWhenScopeConfigHashChanged(self):
        # Given
        scope = self._create_scope()
        old_hash = scope.config_version_hash
        self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31), old_hash)
        scope.fixed_status_values = ['Fixed', 'Verified Fixed']
        scope.save()

        # When
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        self.assertEqual('stale_config', chart.run_metadata.freshness_status)
        self.assertEqual(old_hash, chart.run_metadata.run_config_version_hash)
        self.assertEqual(scope.config_version_hash, chart.run_metadata.current_config_version_hash)
        self.assertEqual([], chart.datasets)
        self.assertIn('does not match the current scope configuration', chart.unavailable_reason)
        self.assertFalse(chart.current_evidence_available)

    def test_shouldRejectDateRangeBeforeAfterOrPartiallyOutsideRunCoverage(self):
        # Given
        scope = self._create_scope()
        self._create_run(scope, date(2026, 8, 10), date(2026, 8, 20), scope.config_version_hash)

        # When
        before_chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 1), date(2026, 8, 9))
        after_chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 21), date(2026, 8, 31))
        overlap_chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 5), date(2026, 8, 15))

        # Then
        self.assertIsNone(before_chart.calculation_run_id)
        self.assertIsNone(after_chart.calculation_run_id)
        self.assertIsNone(overlap_chart.calculation_run_id)

    def test_shouldReturnEvidenceForRequestedRunAndBucketArtifact(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31), scope.config_version_hash)
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            fixed_or_closed_count=1,
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
        )

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
        self.assertEqual(['STDEL-8942'], [row.issue_key for row in result.rows])
        self.assertEqual('Failure in emulation flow', result.rows[0].summary)

    def test_shouldKeepEvidenceFactsStableWhenCurrentIssueChangesAfterRun(self):
        # Given
        scope = self._create_scope()
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31), scope.config_version_hash)
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            fixed_or_closed_count=1,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-3001',
            summary='Changed after run',
            issue_type='Bug',
            status='Reopened',
            severity_value='P1-Critical',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='fixed_or_closed_bugs',
            issue_key='STDEL-3001',
            summary='Original fixed bug',
            status='Fixed',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )

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
        self.assertEqual('Original fixed bug', result.rows[0].summary)
        self.assertEqual('Fixed', result.rows[0].status)

    def test_shouldNotReturnEvidenceForStaleRunWhenScopeConfigChanged(self):
        # Given
        scope = self._create_scope()
        old_hash = scope.config_version_hash
        run = self._create_run(scope, date(2026, 8, 1), date(2026, 8, 31), old_hash)
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            fixed_or_closed_count=1,
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='fixed_or_closed_bugs',
            issue_key='STDEL-3002',
            summary='Old scope evidence',
            status='Fixed',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        scope.fixed_status_values = ['Fixed', 'Verified Fixed']
        scope.save()

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
        self.assertEqual([], result.rows)
        self.assertEqual(0, result.total_count)

    def test_shouldCountBugAsOpenBeforeFutureFixedTransition(self):
        # Given
        scope = self._create_scope()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1000',
            summary='Future fixed bug',
            issue_type='Bug',
            status='Fixed',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1000',
            transitioned_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
            field='status',
            from_value='Open',
            to_value='Fixed',
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        self.assertEqual([1], chart.datasets[0].values)

    def test_shouldHonorExplicitMediumLowValuesWhenClassifyingNewBugs(self):
        # Given
        scope = self._create_scope()
        scope.medium_low_values = ['P3-Medium']
        scope.save()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Known medium bug',
            issue_type='Bug',
            status='Open',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            summary='Unknown severity bug',
            issue_type='Bug',
            status='Open',
            severity_value='P4-Low',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        new_medium_low = next(dataset for dataset in chart.datasets if dataset.series_name == 'new_medium_low')
        self.assertEqual([1], new_medium_low.values)

    def test_shouldUseScopeTimezoneForBucketAssignment(self):
        # Given
        scope = self._create_scope()
        scope.timezone = 'America/Los_Angeles'
        scope.bucket_granularity = JiraScopeConfig.GRANULARITY_DAILY
        scope.save()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1003',
            summary='Late UTC bug',
            issue_type='Bug',
            status='Open',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, 1, 30, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, 1, 30, tzinfo=timezone.utc),
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 3))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 3))

        # Then
        new_medium_low = next(dataset for dataset in chart.datasets if dataset.series_name == 'new_medium_low')
        self.assertEqual([1], new_medium_low.values)

    def test_shouldExcludeResolvedBugFromOpenBacklogWhenResolutionIsTerminal(self):
        # Given
        scope = self._create_scope()
        scope.open_status_values = ['Open']
        scope.fixed_status_values = []
        scope.closed_status_values = []
        scope.fixed_resolution_values = ['Fixed']
        scope.save()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1004',
            summary='Resolved without terminal status',
            issue_type='Bug',
            status='Open',
            resolution_value='Fixed',
            resolved_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        self.assertEqual([0], chart.datasets[0].values)

    def test_shouldHideCriticalHighSeriesWhenSeverityMappingIsAbsent(self):
        # Given
        scope = self._create_scope()
        scope.severity_field = ''
        scope.critical_high_values = []
        scope.save()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1005',
            summary='Bug without severity authority',
            issue_type='Bug',
            status='Open',
            severity_value='',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        series_names = [dataset.series_name for dataset in chart.datasets]
        self.assertNotIn('all_open_critical_high', series_names)
        self.assertNotIn('new_critical_high', series_names)

    def test_shouldNotCountFixedNonBugIssuesWhenScopeJqlIsBroad(self):
        # Given
        scope = self._create_scope()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-2000',
            summary='Task that should not count as bug',
            issue_type='Task',
            status='Fixed',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-2000',
            transitioned_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            field='status',
            from_value='Open',
            to_value='Fixed',
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        fixed_or_closed = next(dataset for dataset in chart.datasets if dataset.series_name == 'fixed_or_closed_bugs')
        self.assertEqual([0], fixed_or_closed.values)

    def test_shouldHonorExplicitOpenStatusAllowList(self):
        # Given
        scope = self._create_scope()
        scope.open_status_values = ['Open']
        scope.save()
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-2001',
            summary='Unmapped active status',
            issue_type='Bug',
            status='In Triage',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )

        # When
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart = bug_trend_api.get_chart(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # Then
        self.assertEqual([0], chart.datasets[0].values)

    def test_shouldExposeConfiguredDisplayFieldsInEvidenceRows(self):
        # Given
        scope = self._create_scope()
        scope.display_fields = ['customfield_bug_type']
        scope.save()
        run = self._create_run(scope, date(2026, 8, 3), date(2026, 8, 9), scope.config_version_hash)
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            fixed_or_closed_count=1,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-2002',
            summary='Bug with subtype',
            issue_type='Bug',
            status='Fixed',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            raw_fields_json={'customfield_bug_type': {'value': 'Emulation'}},
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='fixed_or_closed_bugs',
            issue_key='STDEL-2002',
            summary='Bug with subtype',
            status='Fixed',
            severity_value='P3-Medium',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            extra_fields_json={'customfield_bug_type': 'Emulation'},
        )

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
        self.assertEqual('Emulation', result.rows[0].extra_fields['customfield_bug_type'])

    def _create_scope(self):
        return JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
        )

    def _create_run(self, scope, coverage_start, coverage_end, config_hash):
        return BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=config_hash,
            source_coverage_start=coverage_start,
            source_coverage_end=coverage_end,
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )