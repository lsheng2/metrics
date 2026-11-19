from django.test import TestCase, override_settings
from django.urls import reverse

from bug_metrics.models import BugTrendAuditEvent
from bug_metrics.tests.ai_publication_fixtures import seed_publication_data
from bug_metrics.tests.test_ai_chart_publications import publication_values


@override_settings(METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999')
class TestEmbeddedChartWorkflow(TestCase):
    def test_operator_uses_the_same_read_only_workflow_without_sidecar_or_proof_fields(self):
        seed_publication_data()
        before = BugTrendAuditEvent.objects.count()
        response = self.client.post(reverse('ui_web:ai_dashboard_workflow'), {
            'profile_id': 'chiplet-2a-jira', 'chart_id': 'open_bug_trend',
            'requested_series': 'new_critical_high',
            'range_mode': 'ww', 'range_start': '26WW32', 'range_end': '26WW35',
        })
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'draft_validated')
        self.assertContains(response, 'chiplet-2a-jira')
        for retired in ('sidecar', 'gcx', 'dry_run_proof', 'name="actor"', 'name="dashboard_uid"'):
            self.assertNotIn(retired, response.content.decode().lower())
        self.assertEqual(before, BugTrendAuditEvent.objects.count())

    def test_unsupported_semantic_is_kept_and_not_mapped_to_a_supported_series(self):
        response = self.client.post(reverse('ui_web:ai_dashboard_workflow'), {
            'profile_id': 'nvu-ttl-hsdes', 'chart_id': 'open_bug_trend',
            'requested_series': 'new_critical',
            'range_mode': 'ww', 'range_start': '26WW32', 'range_end': '26WW35',
        })
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'needs_metric_recipe')
        self.assertEqual(['new_critical'], response.context['workflow_result']['request']['requested_series'])

    def test_publish_history_uses_only_new_records_and_marks_supersession(self):
        from bug_metrics.models import AiChartPublication

        old = AiChartPublication.objects.create(**publication_values('old'))
        new = AiChartPublication.objects.create(**publication_values('new', supersedes=old))
        BugTrendAuditEvent.objects.create(
            event_type='ai_grafana_published', actor='legacy-actor', request_summary={'dashboard_uid': 'legacy'},
        )
        response = self.client.get('/api/ai-publish-history/')
        self.assertEqual(200, response.status_code)
        rows = {item['publication_id']: item for item in response.json()['items']}
        self.assertEqual({str(old.id), str(new.id)}, set(rows))
        self.assertFalse(rows[str(old.id)]['latest'])
        self.assertTrue(rows[str(new.id)]['latest'])
        self.assertEqual('approval-new', rows[str(new.id)]['approval_id'])

    def test_old_ai_dashboard_api_paths_are_not_routes(self):
        paths = (
            'identity', 'catalog', 'intent/validate', 'render-config/validate',
            'artifacts/validate', 'workflow', 'gcx/precondition', 'gcx/publication-callback',
            'publish-approval', 'publish-approval/decision', 'publish-demo', 'publish-history', 'context',
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(404, self.client.get(f'/api/ai-dashboard/{path}/').status_code)
