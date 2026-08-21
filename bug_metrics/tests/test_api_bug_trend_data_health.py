from datetime import date, datetime, timezone
from dataclasses import dataclass
from unittest.mock import patch

from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig


@dataclass(slots=True)
class FailingJiraHistoryApi:
    def list_issues(self, scope):
        raise RuntimeError('history unavailable')


@dataclass(slots=True)
class FakeJiraHistoryContainer:
    jira_history_api: FailingJiraHistoryApi


class TestBugTrendCalculationHealthApi(TestCase):
    def test_shouldExposeCalculationHealthFromRunArtifactsWithoutRecalculation(self):
        # Given
        fresh_scope = self._create_scope('STDEL fresh')
        fresh_run = self._create_run(fresh_scope, BugTrendCalculationRun.STATUS_COMPLETED, fresh_scope.config_version_hash)
        stale_scope = self._create_scope('STDEL stale')
        old_hash = stale_scope.config_version_hash
        stale_scope.fixed_status_values = ['Fixed', 'Verified Fixed']
        stale_scope.save()
        stale_run = self._create_run(stale_scope, BugTrendCalculationRun.STATUS_COMPLETED, old_hash)
        failed_scope = self._create_scope('STDEL failed')
        failed_run = self._create_run(failed_scope, BugTrendCalculationRun.STATUS_FAILED, failed_scope.config_version_hash)
        before_count = BugTrendCalculationRun.objects.count()

        # When
        result = bug_trend_api.list_calculation_health()

        # Then
        self.assertEqual(before_count, BugTrendCalculationRun.objects.count())
        health_by_scope = {item.scope_name: item for item in result}
        self.assertEqual(str(fresh_run.id), health_by_scope['STDEL fresh'].calculation_run_id)
        self.assertEqual('fresh', health_by_scope['STDEL fresh'].freshness_status)
        self.assertEqual(str(stale_run.id), health_by_scope['STDEL stale'].calculation_run_id)
        self.assertEqual('stale_config', health_by_scope['STDEL stale'].freshness_status)
        self.assertEqual(old_hash, health_by_scope['STDEL stale'].run_config_version_hash)
        self.assertEqual(stale_scope.config_version_hash, health_by_scope['STDEL stale'].current_config_version_hash)
        self.assertEqual(str(failed_run.id), health_by_scope['STDEL failed'].calculation_run_id)
        self.assertEqual(BugTrendCalculationRun.STATUS_FAILED, health_by_scope['STDEL failed'].freshness_status)

    def test_shouldReportEnabledScopeWithoutCalculationRun(self):
        # Given
        scope = self._create_scope('STDEL missing')

        # When
        result = bug_trend_api.list_calculation_health()

        # Then
        self.assertEqual(1, len(result))
        self.assertEqual(scope.id, result[0].scope_id)
        self.assertEqual('no_run', result[0].status)
        self.assertEqual('missing', result[0].freshness_status)

    def test_shouldMarkCalculationRunFailedWhenHistoryMaterializationFails(self):
        # Given
        scope = self._create_scope('STDEL failed producer')
        fake_container = FakeJiraHistoryContainer(FailingJiraHistoryApi())

        # When
        with patch('bug_metrics.app.api.calculation.jira_history_container', fake_container):
            with self.assertRaises(RuntimeError):
                bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 1), date(2026, 8, 31))

        # Then
        run = BugTrendCalculationRun.objects.get(scope=scope)
        self.assertEqual(BugTrendCalculationRun.STATUS_FAILED, run.status)
        self.assertIsNotNone(run.completed_at)

    def _create_scope(self, name):
        return JiraScopeConfig.objects.create(
            name=name,
            jql='project = STDEL',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
        )

    def _create_run(self, scope, status, config_hash):
        return BugTrendCalculationRun.objects.create(
            scope=scope,
            status=status,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc) if status == BugTrendCalculationRun.STATUS_COMPLETED else None,
            config_version_hash=config_hash,
            source_coverage_start=date(2026, 8, 1),
            source_coverage_end=date(2026, 8, 31),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )