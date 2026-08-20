from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.app.api.chart_catalog import AiChartDraftRequest
from bug_metrics.models import BugTrendAuditEvent, BugTrendChartDefinition, BugTrendChartPublishRequest


class TestAiChartGovernance(TestCase):
    def test_shouldRejectAiDraftSpecWithSqlOrSecretsBeforeCatalogEntryIsCreated(self):
        # When / Then
        with self.assertRaises(ValueError):
            bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
                chart_id='ai_unsafe',
                title='Unsafe AI Chart',
                renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
                integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
                evidence_contract_id='default_bug_trend_bucket_series',
                spec={'query': 'select * from jira_history_issue', 'token': 'do-not-store'},
            ))
        self.assertFalse(BugTrendChartDefinition.objects.filter(chart_id='ai_unsafe').exists())

    def test_shouldCreateValidatedAiDraftAndPublishPersonalChartWithAudit(self):
        # Given
        draft = bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
            chart_id='ai_daily_bug_in',
            title='AI Daily Bug In',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract_id='default_bug_trend_bucket_series',
            spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'series': ['new_critical_high']},
            actor='local_operator',
        ))

        # When
        result = bug_trend_api.publish_chart(draft.chart_id, actor='local_operator', governance_mode='personal')

        # Then
        self.assertTrue(result.published)
        self.assertEqual(BugTrendChartDefinition.STATUS_PUBLISHED, result.status)
        chart = BugTrendChartDefinition.objects.get(chart_id='ai_daily_bug_in')
        self.assertTrue(chart.enabled)
        self.assertEqual('personal', chart.visibility)
        event = BugTrendAuditEvent.objects.get(event_type='chart_published', chart_id='ai_daily_bug_in')
        self.assertEqual('local_operator', event.actor)
        self.assertIsNone(event.scope)
        self.assertIn('ai_daily_bug_in', [item.chart_id for item in bug_trend_api.list_enabled_charts()])

    def test_shouldKeepCloudPublishPendingUntilApprovalBoundary(self):
        # Given
        draft = bug_trend_api.create_ai_chart_draft(AiChartDraftRequest(
            chart_id='ai_cloud_chart',
            title='AI Cloud Chart',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract_id='default_bug_trend_bucket_series',
            spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'series': ['all_open_bugs']},
            actor='local_operator',
        ))

        # When
        result = bug_trend_api.publish_chart(draft.chart_id, actor='local_operator', governance_mode='cloud')

        # Then
        self.assertFalse(result.published)
        self.assertEqual(BugTrendChartPublishRequest.STATUS_PENDING, result.status)
        request = BugTrendChartPublishRequest.objects.get(chart__chart_id='ai_cloud_chart')
        self.assertEqual(BugTrendChartPublishRequest.STATUS_PENDING, request.status)
        chart = BugTrendChartDefinition.objects.get(chart_id='ai_cloud_chart')
        self.assertFalse(chart.enabled)
        self.assertNotIn('ai_cloud_chart', [item.chart_id for item in bug_trend_api.list_enabled_charts()])