from django.core.management import call_command
from django.test import TestCase

from bug_metrics.app.api import ProviderChartAggregateQuery, bug_trend_api
from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue


class TestSeedBugTrendSampleProviderParity(TestCase):
    def test_shouldSeedCanonicalJiraFirstProviderProfileForParityDashboard(self):
        # When
        call_command('seed_bug_trend_sample', verbosity=0)

        # Then
        scope = JiraScopeConfig.objects.get(name='chiplet-2a-jira')
        self.assertEqual('chiplet_ip', scope.ip)
        self.assertEqual('chiplet', scope.project_label)
        self.assertEqual('2a', scope.milestone_field)
        self.assertEqual('project = "131600" AND component = "team_int_qemu"', scope.jql)
        self.assertTrue(JiraIssue.objects.filter(scope=scope, is_in_current_scope=True).exists())
        self.assertTrue(BugTrendCalculationRun.objects.filter(scope=scope, status=BugTrendCalculationRun.STATUS_COMPLETED).exists())

    def test_shouldSeedJiraFirstAiPublishCoverageForTargetRange(self):
        # When
        call_command('seed_bug_trend_sample', verbosity=0)

        # Then
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                begin_ww='26WW32',
                end_ww='26WW35',
                chart_id='open_bug_trend',
            )
        )
        self.assertEqual('supported', result.status)
        self.assertTrue(result.grafana_rows)
        self.assertTrue(any(row.get('new_critical_high', 0) > 0 for row in result.grafana_rows))
