from datetime import date, datetime, timezone

from django.test import TestCase, override_settings
from django.urls import reverse

from bug_metrics.models import BugTrendAuditEvent
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

        def test_shouldRenderChartSelectorFromMetricsCatalog(self):
            # Given
            scope, _, _ = self._seed_trend_data()

            # When
            response = self.client.get(reverse('ui_web:bug_trend'), {
                'scope_id': scope.id,
                'begin': '2026-08-03',
                'end': '2026-08-09',
                'chart_id': 'default_bug_trend',
            })

            # Then
            content = response.content.decode()
            self.assertEqual(200, response.status_code)
            self.assertIn('name="chart_id"', content)
            self.assertIn('value="default_bug_trend" selected', content)
            self.assertIn('Default Bug Trend', content)

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

    def test_shouldRenderEvidenceFiltersAndExportLinkWithCurrentQueryState(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'all_open_bugs',
            'owner': 'Alice',
                'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Filter evidence', content)
        self.assertIn('Export CSV', content)
        self.assertIn(f'bucket={bucket.id}', content)
        self.assertIn('series=all_open_bugs', content)
        self.assertIn('owner=Alice', content)
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

    def test_shouldExposeBugTrendChartDataJsonForGrafanaSurface(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(scope.id, payload['scope_id'])
        self.assertEqual(str(run.id), payload['calculation_run_id'])
        self.assertEqual({
            'calculation_run_id': str(run.id),
            'run_config_version_hash': run.config_version_hash,
            'current_config_version_hash': scope.config_version_hash,
            'freshness_status': 'fresh',
            'source_coverage_start': '2026-08-03',
            'source_coverage_end': '2026-08-09',
            'completed_at': '2026-08-19T00:00:00+00:00',
        }, payload['run_metadata'])
        self.assertTrue(payload['current_evidence_available'])
        self.assertEqual([str(bucket.id)], payload['bucket_ids'])
        self.assertIn('fixed_or_closed_bugs', [dataset['series_name'] for dataset in payload['datasets']])
        self.assertIn({
            'calculation_run_id': str(run.id),
            'bucket_id': str(bucket.id),
            'series_name': 'fixed_or_closed_bugs',
            'label': '26WW32',
            'value': -1,
            'type': 'bar',
            'color': '#bdbdbd',
        }, payload['points'])

    def test_shouldRejectUnapprovedChartDataApiQueryParams(self):
        # Given
        scope, run, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'run': str(run.id),
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual(['run'], response.json()['unknown_params'])

    def test_shouldExposeBugTrendEvidenceJsonForGrafanaSurface(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
        })

        # Then
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual('fixed_or_closed_bugs tickets for 26WW32', payload['selection_title'])
        self.assertEqual(1, payload['total_count'])
        self.assertEqual(['STDEL-1002'], [row['issue_key'] for row in payload['rows']])

    def test_shouldRequireRunForBugTrendEvidenceApi(self):
        # Given
        scope, _, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual(['run'], response.json()['missing_params'])

    def test_shouldNotExposeStaleRunEvidenceThroughJsonApi(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        scope.fixed_status_values = ['Fixed', 'Verified Fixed']
        scope.save()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
        })

        # Then
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(0, payload['total_count'])
        self.assertEqual([], payload['rows'])

    def test_shouldExportFilteredEvidenceCsvAndRecordAuditEvent(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_export'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'all_open_bugs',
            'owner': 'Alice',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual('text/csv', response['Content-Type'])
        self.assertIn('attachment; filename="bug-trend-evidence-scope-', response['Content-Disposition'])
        self.assertIn('issue_key,summary,series_name,status,severity,owner,component,created_at,updated_at', content)
        self.assertIn('STDEL-1001', content)
        self.assertNotIn('STDEL-1002', content)
        event = BugTrendAuditEvent.objects.get(event_type=BugTrendAuditEvent.EVENT_EVIDENCE_EXPORTED)
        self.assertEqual(scope, event.scope)
        self.assertEqual(str(run.id), event.calculation_run_id)
        self.assertEqual('default_bug_trend', event.chart_id)
        self.assertEqual('Alice', event.request_summary['filters']['owner'])
        self.assertEqual(1, event.request_summary['row_count'])

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