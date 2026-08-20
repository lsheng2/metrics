from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig


class TestBugTrendApiContracts(TestCase):
    def test_shouldReturnBadRequestForMalformedChartDataDate(self):
        # Given
        scope, _ = self._seed_run()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_chart_data_api'), {
            'scope_id': scope.id,
            'begin': 'not-date',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual('begin must be an ISO date.', response.json()['error'])

    def test_shouldReturnBadRequestForMalformedEvidenceDate(self):
        # Given
        scope, run = self._seed_run()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': 'not-date',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual('end must be an ISO date.', response.json()['error'])

    def test_shouldReturnBadRequestForMalformedExportDate(self):
        # Given
        scope, run = self._seed_run()

        # When
        response = self.client.get(reverse('ui_web:bug_trend_evidence_export'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': 'not-date',
            'end': '2026-08-09',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual('begin must be an ISO date.', response.json()['error'])

    def _seed_run(self):
        scope = JiraScopeConfig.objects.create(
            name='STDEL api contract',
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
        return scope, run