from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from bug_metrics.models import BugTrendBucket, BugTrendCalculationRun, JiraScopeConfig
from jira_sync.out.jira_scope_issue_adapter import create_jira_client
from ui_web.container import ui_web_container


@override_settings(METRICS_JIRA_SERVER_URL=None, METRICS_JIRA_EMAIL=None, METRICS_JIRA_API_TOKEN=None)
class TestBugTrendWithoutProviderSettings(TestCase):
    def test_shouldRenderLocalTrendDataWithoutOpeningJiraClient(self):
        # Given
        scope, run = self._seed_trend_data()
        query = {'scope_id': scope.id, 'begin': '2026-08-03', 'end': '2026-08-09'}
        chart_query = {**query, 'chart_id': 'default_bug_trend'}

        # When
        with patch.object(ui_web_container, '_bug_trend_facade', None), \
                patch('jira_sync.container.create_jira_client', wraps=create_jira_client) as client_factory:
            bug_trend = self.client.get(reverse('ui_web:bug_trend'), query)
            workbench = self.client.get(reverse('ui_web:workbench'), chart_query)
            chart_data = self.client.get(reverse('ui_web:chart_data_api'), chart_query)

        # Then
        self.assertEqual([200, 200, 200], [bug_trend.status_code, workbench.status_code, chart_data.status_code])
        self.assertEqual(str(run.id), chart_data.json()['calculation_run_id'])
        self.assertEqual(0, client_factory.call_count)

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
        BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            fixed_or_closed_count=1,
            open_count=1,
        )
        return scope, run
