from dataclasses import replace
from datetime import date, datetime, timezone
import json

from django.test import TestCase, override_settings

from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import AiChartPublication, BugTrendAuditEvent
from bug_metrics.tests.ai_publication_fixtures import chart_request, seed_publication_data
from jira_history.models import JiraIssue


@override_settings(METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999')
class TestAiChartPreview(TestCase):
    def test_preview_is_deterministic_read_only_and_keeps_approved_metadata(self):
        from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService

        seed_publication_data()
        audit_count = BugTrendAuditEvent.objects.count()
        service = AiChartWorkflowService()
        first = service.preview(chart_request())
        second = service.preview(chart_request())
        self.assertTrue(first.ready, first.workflow)
        self.assertEqual(first.content, second.content)
        self.assertEqual('draft_validated', first.workflow['status'])
        self.assertEqual('jira', first.content['publication']['provider_id'])
        self.assertEqual('chiplet-2a-jira', first.content['publication']['profile_id'])
        self.assertEqual(['new_critical_high'], first.content['publication']['requested_series'])
        self.assertEqual('26WW32', first.content['publication']['range_start'])
        self.assertEqual(64, len(first.content['publication']['data_fingerprint']))
        self.assertEqual(first.content['dashboard']['uid'], first.content['target']['uid'])
        self.assertEqual(audit_count, BugTrendAuditEvent.objects.count())
        self.assertEqual(0, AiChartPublication.objects.count())

    def test_changed_data_changes_fingerprint_while_chart_urls_are_unchanged(self):
        from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService

        scope, _ = seed_publication_data()
        service = AiChartWorkflowService()
        first = service.preview(chart_request())
        JiraIssue.objects.create(
            scope=scope, issue_key='SAMPLE-2', summary='Another synthetic issue',
            issue_type='Bug', status='Open', severity_value='P2-High',
            created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 30))
        second = service.preview(chart_request())
        self.assertTrue(first.ready and second.ready)
        self.assertEqual(first.content['dashboard'], second.content['dashboard'])
        self.assertNotEqual(first.content['publication']['data_fingerprint'],
                            second.content['publication']['data_fingerprint'])

    def test_row_order_and_transient_cache_age_do_not_change_data_fingerprint(self):
        from bug_metrics.app.api.ai_chart_workflow import data_fingerprint
        from bug_metrics.app.api.provider_aggregates import ProviderChartAggregateService
        from bug_metrics.app.api.provider_aggregate_contracts import ProviderChartAggregateQuery

        seed_publication_data()
        result = ProviderChartAggregateService().get_aggregates(ProviderChartAggregateQuery(
            provider_id='jira', profile_id='chiplet-2a-jira',
            begin_ww='26WW32', end_ww='26WW35', chart_id='open_bug_trend',
        ))
        self.assertEqual('supported', result.status, result.reason)
        self.assertTrue(result.grafana_rows)
        reordered = replace(
            result, grafana_rows=list(reversed(result.grafana_rows)),
            run_metadata={**result.run_metadata, 'cache_age_seconds': 999, 'checked_at': 'later'},
        )
        self.assertEqual(data_fingerprint(result), data_fingerprint(reordered))

    def test_missing_data_and_unsupported_semantics_never_make_a_ready_preview(self):
        from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService

        service = AiChartWorkflowService()
        missing = service.preview(chart_request())
        unsupported = service.preview(chart_request(
            profile_id='nvu-ttl-hsdes', requested_series=('new_critical',),
        ))
        self.assertFalse(missing.ready)
        self.assertIsNone(missing.content)
        self.assertFalse(unsupported.ready)
        self.assertEqual('needs_metric_recipe', unsupported.workflow['status'])
        self.assertEqual(['new_critical'], unsupported.workflow['request']['requested_series'])
        self.assertEqual(0, AiChartPublication.objects.count())

    def test_empty_or_unsafe_draft_is_rejected_instead_of_replaced_with_a_recipe(self):
        from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService

        seed_publication_data()
        service = AiChartWorkflowService()
        for draft in ({}, {'password': 'synthetic-forbidden', 'sections': []}):
            with self.subTest(draft=draft):
                result = service.preview(chart_request(render_config=draft))
                self.assertFalse(result.ready)
                self.assertTrue(result.workflow['findings'])
                self.assertNotIn('synthetic-forbidden', json.dumps(result.workflow))

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://user:synthetic-secret@127.0.0.1:39999')
    def test_credential_bearing_target_is_not_exposed_in_preview(self):
        from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService

        seed_publication_data()
        result = AiChartWorkflowService().preview(chart_request())
        self.assertFalse(result.ready)
        self.assertNotIn('synthetic-secret', json.dumps(result.workflow))
