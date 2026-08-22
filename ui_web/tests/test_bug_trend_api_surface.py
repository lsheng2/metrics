from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.app.api import BugTrendPageQueryState, bug_trend_api
from bug_metrics.app.api.chart_catalog import AiChartDraftRequest
from bug_metrics.models import BugTrendAuditEvent
from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, BugTrendChartDefinition, BugTrendEvidenceContract, JiraScopeConfig


class TestBugTrendApiSurface(TestCase):
    def test_shouldExposeBugTrendChartDataJsonForGrafanaSurface(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(scope.id, payload['scope_id'])
        self.assertEqual('default_bug_trend', payload['chart_id'])
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
        point = next(item for item in payload['points'] if item['series_name'] == 'fixed_or_closed_bugs')
        self.assertEqual(str(run.id), point['calculation_run_id'])
        self.assertEqual(str(bucket.id), point['bucket_id'])
        self.assertEqual('26WW32', point['bucket_label'])
        self.assertEqual('2026-08-03', point['bucket_start'])
        self.assertEqual('2026-08-09', point['bucket_end'])
        self.assertEqual('weekly', point['bucket_granularity'])
        self.assertEqual(-1, point['value'])
        self.assertEqual('bar', point['type'])
        self.assertEqual('#bdbdbd', point['color'])
        self.assertEqual([{
            'calculation_run_id': str(run.id),
            'bucket_id': str(bucket.id),
            'bucket_label': '26WW32',
            'bucket_start': '2026-08-03',
            'bucket_end': '2026-08-09',
            'bucket_granularity': 'weekly',
            'all_open_bugs': 2,
            'all_open_critical_high': 0,
            'new_critical_high': 0,
            'new_medium_low': 0,
            'fixed_or_closed_bugs': -1,
        }], payload['grafana_rows'])

    def test_shouldAcceptChartIdOnBugTrendChartDataJsonApi(self):
        # Given
        scope, _, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual('default_bug_trend', response.json()['chart_id'])
        self.assertEqual('0.1', response.json()['contract_version'])

    def test_shouldRejectUnapprovedChartDataApiQueryParams(self):
        # Given
        scope, run, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'run': str(run.id),
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual(['run'], response.json()['unknown_params'])

    def test_shouldRenderSelectedCatalogChartSpecInsteadOfDefaultSeries(self):
        # Given
        scope, run, _ = self._seed_trend_data()
        draft = bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
            chart_id='ai_open_only',
            title='AI Open Only',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract_id='default_bug_trend_bucket_series',
            spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'series': ['all_open_bugs']},
        ))
        bug_trend_api.publish_chart(draft.chart_id)

        # When
        response = self.client.get(reverse('ui_web:chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'ai_open_only',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('ai_open_only', payload['chart_id'])
        self.assertEqual(['all_open_bugs'], [dataset['series_name'] for dataset in payload['datasets']])
        self.assertEqual(str(run.id), payload['calculation_run_id'])

    def test_shouldFilterRangeEvidenceToSelectedCatalogChartSeries(self):
        # Given
        scope, run, _ = self._seed_trend_data()
        draft = bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
            chart_id='ai_open_evidence_only',
            title='AI Open Evidence Only',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract_id='default_bug_trend_bucket_series',
            spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'series': ['all_open_bugs']},
        ))
        bug_trend_api.publish_chart(draft.chart_id)

        # When
        response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'ai_open_evidence_only',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(['STDEL-1001'], [row['issue_key'] for row in payload['rows']])
        self.assertEqual(['all_open_bugs'], [row['series_name'] for row in payload['rows']])

    def test_shouldExportOnlySelectedCatalogChartSeries(self):
        # Given
        scope, run, _ = self._seed_trend_data()
        draft = bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
            chart_id='ai_open_export_only',
            title='AI Open Export Only',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract_id='default_bug_trend_bucket_series',
            spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'series': ['all_open_bugs']},
        ))
        bug_trend_api.publish_chart(draft.chart_id)

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_export'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'ai_open_export_only',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('STDEL-1001', content)
        self.assertNotIn('STDEL-1002', content)

    def test_shouldReturnBadRequestForUnknownChartDataApiChartId(self):
        # Given
        scope, _, _ = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:chart_data_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'unknown_chart',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual('Unknown or unpublished Bug Trend chart.', response.json()['error'])

    def test_shouldRejectEvidenceExportForUnpublishedChartId(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When / Then
        with self.assertRaises(BugTrendChartDefinition.DoesNotExist):
            bug_trend_api.export_evidence_tickets(BugTrendPageQueryState(
                scope_id=scope.id,
                begin=date(2026, 8, 3),
                end=date(2026, 8, 9),
                calculation_run_id=str(run.id),
                selected_bucket_id=str(bucket.id),
                selected_series_name='all_open_bugs',
                active_chart_id='unknown_chart',
            ))

    def test_shouldReturnBadRequestForUnknownEvidenceApiChartId(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'all_open_bugs',
            'chart_id': 'unknown_chart',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual('Unknown or unpublished Bug Trend chart.', response.json()['error'])

    def test_shouldReturnBadRequestForSummaryOnlyEvidenceApiChartId(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        self._publish_summary_only_chart()

        # When
        response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'all_open_bugs',
            'chart_id': 'summary_only_chart',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertIn('Summary-only chart has no ticket evidence.', response.json()['error'])

    def test_shouldReturnBadRequestForUnknownExportChartId(self):
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
            'chart_id': 'unknown_chart',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual('Unknown or unpublished Bug Trend chart.', response.json()['error'])

    def test_shouldReturnBadRequestForSummaryOnlyExportChartId(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        self._publish_summary_only_chart()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_export'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'all_open_bugs',
            'chart_id': 'summary_only_chart',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertIn('Summary-only chart has no ticket evidence.', response.json()['error'])

    def test_shouldExposeBugTrendEvidenceJsonForGrafanaSurface(self):
        # Given
        scope, run, bucket = self._seed_trend_data()

        # When
        response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'default_bug_trend',
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
        response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'default_bug_trend',
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
        response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'default_bug_trend',
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

    def _publish_summary_only_chart(self):
        contract = BugTrendEvidenceContract.objects.create(
            contract_id='summary_only_contract',
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
