from datetime import date, datetime, timezone

from django.test import TestCase

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters, bug_trend_api
from bug_metrics.models import BugTrendAuditEvent, BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig


class TestBugTrendEvidenceExport(TestCase):
    def test_shouldExportExactlyCurrentEvidenceRowsAndRecordAuditEvent(self):
        # Given
        scope, run, bucket = self._seed_trend_data()
        state = BugTrendPageQueryState(
            scope.id,
            date(2026, 8, 3),
            date(2026, 8, 9),
            calculation_run_id=str(run.id),
            selected_bucket_id=str(bucket.id),
            selected_series_name='all_open_bugs',
            list_filters=BugTrendTicketListFilters(owner='Alice'),
            active_chart_id='default_bug_trend',
        )

        # When
        evidence = bug_trend_api.get_evidence_tickets(state)
        export = bug_trend_api.export_evidence_tickets(state, actor='local_operator')

        # Then
        self.assertEqual([row.issue_key for row in evidence.rows], self._csv_issue_keys(export.content))
        self.assertEqual(evidence.shown_count, export.row_count)
        event = BugTrendAuditEvent.objects.get(event_type=BugTrendAuditEvent.EVENT_EVIDENCE_EXPORTED)
        self.assertEqual('local_operator', event.actor)
        self.assertEqual(scope, event.scope)
        self.assertEqual(str(run.id), event.calculation_run_id)
        self.assertEqual('default_bug_trend', event.chart_id)
        self.assertEqual('Alice', event.request_summary['filters']['owner'])
        self.assertEqual(str(bucket.id), event.request_summary['selected_bucket_id'])
        self.assertEqual('all_open_bugs', event.request_summary['selected_series_name'])
        self.assertEqual(evidence.shown_count, event.request_summary['row_count'])

    def _csv_issue_keys(self, content):
        lines = content.strip().splitlines()
        return [line.split(',')[0] for line in lines[1:]]

    def _seed_trend_data(self):
        scope = JiraScopeConfig.objects.create(
            name='STDEL export',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
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
            open_count=2,
        )
        self._create_membership(scope, run, bucket, 'STDEL-7001', 'Alice')
        self._create_membership(scope, run, bucket, 'STDEL-7002', 'Bob')
        return scope, run, bucket

    def _create_membership(self, scope, run, bucket, issue_key, owner):
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='all_open_bugs',
            issue_key=issue_key,
            summary=f'{issue_key} summary',
            status='Open',
            severity_value='P3-Medium',
            owner_value=owner,
            component_value='emulation',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )