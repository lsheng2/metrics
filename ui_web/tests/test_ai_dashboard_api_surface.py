import json
from unittest.mock import patch

from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from bug_metrics.app.api import DashboardCompositionIntent, bug_trend_api
from bug_metrics.models import BugTrendAuditEvent


class TestAiDashboardApiSurface(TestCase):
    def test_shouldExposeAiDashboardCatalogWithoutProviderSecrets(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_catalog_api'), {
            'profile_id': 'nvu-ttl-hsdes',
        })

        payload = response.json()
        serialized_payload = json.dumps(payload).lower()
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertEqual('profile_catalog', payload['catalog_type'])
        self.assertEqual('nvu-ttl-hsdes', payload['profiles'][0]['profile_id'])
        self.assertIn('open_bug_trend', payload['chart_recipes'])
        self.assertNotIn('native_query_text', serialized_payload)
        self.assertNotIn('password', serialized_payload)
        self.assertNotIn('token', serialized_payload)
        self.assertNotIn('api_key', serialized_payload)

    def test_shouldValidateUnsupportedAiCompositionIntentAsNeedsMetricRecipe(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_intent_validation_api'),
            data=json.dumps({
                'profile_id': 'nvu-ttl-hsdes',
                'dashboard_uid': 'ip-quality-dashboard',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical'],
                'range_mode': 'ww',
                'range_start': '26WW10',
                'range_end': '26WW35',
                'output_type': 'render_config_draft',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('needs_metric_recipe', payload['status'])
        self.assertFalse(payload['valid'])
        self.assertEqual(['new_critical'], payload['needs_metric_recipe']['requested_series'])
        self.assertNotIn('draft_render_config', payload)

    def test_shouldValidateSupportedAiCompositionIntentAsDraftRenderConfig(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_intent_validation_api'),
            data=json.dumps({
                'profile_id': 'nvu-ttl-hsdes',
                'dashboard_uid': 'ip-quality-dashboard',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical_high'],
                'range_mode': 'ww',
                'range_start': '26WW10',
                'range_end': '26WW35',
                'output_type': 'render_config_draft',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        payload = response.json()
        panel = payload['draft_render_config']['sections'][0]['panels'][0]
        self.assertEqual(200, response.status_code)
        self.assertEqual('draft_validated', payload['status'])
        self.assertTrue(payload['valid'])
        self.assertEqual(['new_critical_high'], panel['value_fields'])

    def test_shouldPreviewValidatedRenderConfigWithGrafanaValidator(self):
        draft = bug_trend_api.validate_ai_dashboard_composition_intent(
            DashboardCompositionIntent(
                profile_id='nvu-ttl-hsdes',
                dashboard_uid='ip-quality-dashboard',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW10',
                range_end='26WW35',
                output_type='render_config_draft',
                actor='ai_sidecar',
            )
        )['draft_render_config']

        response = self.client.post(
            reverse('ui_web:ai_dashboard_render_config_validation_api'),
            data=json.dumps({'draft_render_config': draft}),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('draft_validated', payload['status'])
        self.assertTrue(payload['valid'])
        self.assertEqual('ip-quality-dashboard', payload['dashboard_preview']['dashboard_uid'])
        self.assertGreater(payload['dashboard_preview']['panel_count'], 0)

    def test_shouldBlockGcxPreconditionBeforeMutationForInvalidDraft(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_gcx_precondition_api'),
            data=json.dumps({
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
                'draft_render_config': {
                    'dashboard_uid': 'ip-quality-dashboard',
                    'title': 'Invalid Draft',
                    'profile_variable': 'profile_id',
                    'variables': [],
                    'range_controls': {'modes': ['ww']},
                    'sections': [{
                        'id': 'quality',
                        'title': 'Quality',
                        'panels': [{
                            'panel_id': '1',
                            'title': 'Invalid New Critical',
                            'type': 'timeseries',
                            'layout': {'x': 0, 'y': 0, 'w': 12, 'h': 8},
                            'chart_recipe_ref': {'chart_id': 'open_bug_trend', 'chart_version': 1},
                            'provider_binding': 'selected_provider_quality',
                            'render_root': 'grafana_rows',
                            'render_shape': 'wide_bucket_series',
                            'category_field': 'bucket_label',
                            'value_fields': ['new_critical'],
                            'evidence_capability': 'bucket_series',
                        }],
                    }],
                },
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertFalse(payload['mutation_allowed'])
        self.assertTrue(payload['findings'])

    def test_shouldRecordGcxPublicationCallbackAudit(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_gcx_publication_callback_api'),
            data=json.dumps({
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
                'dashboard_uid': 'ip-quality-dashboard',
                'artifact_ref': 'ai-base-artifact://run-123/ip-quality-dashboard.json',
                'mutation_status': 'succeeded',
                'correlation_id': 'corr-123',
                'dry_run_proof_id': 'proof-123',
            }),
            content_type='application/json',
        )

        payload = response.json()
        event = BugTrendAuditEvent.objects.get(event_type='ai_gcx_publication_callback_recorded')
        self.assertEqual(200, response.status_code)
        self.assertEqual('recorded', payload['status'])
        self.assertEqual('corr-123', payload['correlation_id'])
        self.assertEqual('ai_sidecar', event.actor)
        self.assertEqual('ip-quality-dashboard', event.request_summary['dashboard_uid'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldPublishApprovedAiDashboardDraftToGrafanaAndReturnUrl(self):
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'imported', 'uid': 'ai-open-bug-trend-demo'}

            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=json.dumps({
                    'profile_id': 'chiplet-2a-jira',
                    'dashboard_uid': 'ai-open-bug-trend-demo',
                    'chart_id': 'open_bug_trend',
                    'requested_series': ['new_critical_high'],
                    'range_mode': 'ww',
                    'range_start': '26WW32',
                    'range_end': '26WW35',
                    'operation': 'grafana_import',
                    'actor': 'ai_sidecar',
                    'approval_id': 'approval-local-demo',
                    'dry_run_proof_id': 'dryrun-local-demo',
                }),
                content_type='application/json',
            )

        payload = response.json()
        event = BugTrendAuditEvent.objects.get(event_type='ai_gcx_publication_callback_recorded')
        imported_dashboard = importer.call_args.args[1]
        self.assertEqual(200, response.status_code)
        self.assertEqual('published', payload['status'])
        self.assertEqual('ai-open-bug-trend-demo', payload['dashboard_uid'])
        self.assertIn('/d/ai-open-bug-trend-demo/', payload['dashboard_url'])
        self.assertEqual('recorded', payload['audit']['status'])
        self.assertEqual('dryrun-local-demo', event.request_summary['dry_run_proof_id'])
        self.assertEqual('ai-open-bug-trend-demo', imported_dashboard['uid'])

    def test_shouldRejectAiDashboardPublishWithoutApprovalAndProof(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_demo_api'),
            data=json.dumps({
                'profile_id': 'chiplet-2a-jira',
                'dashboard_uid': 'ai-open-bug-trend-demo',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical_high'],
                'range_mode': 'ww',
                'range_start': '26WW32',
                'range_end': '26WW35',
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        self.assertEqual(400, response.status_code)
        self.assertIn('approval_id', response.json()['error'])
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_callback_recorded').exists())

    def test_shouldRejectIncompleteGcxPublicationCallbackWithoutAuditRecord(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_gcx_publication_callback_api'),
            data=json.dumps({
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
                'dashboard_uid': 'ip-quality-dashboard',
                'artifact_ref': 'ai-base-artifact://run-123/ip-quality-dashboard.json',
                'mutation_status': 'succeeded',
            }),
            content_type='application/json',
        )

        self.assertEqual(400, response.status_code)
        self.assertIn('correlation_id', response.json()['error'])
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_callback_recorded').exists())

    def test_shouldExposeSafeEvidenceContextForAiBase(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_context_api'), {
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
            'begin_ww': '26WW32',
            'end_ww': '26WW35',
            'chart_id': 'open_bug_trend',
        })

        payload = response.json()
        serialized_payload = json.dumps(payload).lower()
        chart = payload['charts'][0]
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.1', payload['contract_version'])
        self.assertEqual('nvu-ttl-hsdes', payload['query_state']['profile_id'])
        self.assertEqual('open_bug_trend', chart['chart_id'])
        self.assertEqual(1, chart['chart_version'])
        self.assertIn('mapping_version', chart['provider_provenance'])
        self.assertIn('fact_snapshot_id', chart)
        self.assertIn('freshness_status', payload['provider_facts_context'])
        self.assertNotIn('native_query_text', serialized_payload)
        self.assertNotIn('password', serialized_payload)
        self.assertNotIn('token', serialized_payload)
        self.assertNotIn('api_key', serialized_payload)

    def test_shouldRunHsdesAiWorkflowForSupportedSeriesWithPreconditionPreview(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_workflow_api'),
            data=json.dumps({
                'profile_id': 'nvu-ttl-hsdes',
                'dashboard_uid': 'ip-quality-dashboard',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical_high'],
                'range_mode': 'ww',
                'range_start': '26WW10',
                'range_end': '26WW35',
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        payload = response.json()
        serialized_payload = json.dumps(payload).lower()
        self.assertEqual(200, response.status_code)
        self.assertEqual('draft_validated', payload['intent_validation']['status'])
        self.assertEqual('draft_validated', payload['render_validation']['status'])
        self.assertEqual('precondition_passed', payload['gcx_precondition']['status'])
        self.assertTrue(payload['gcx_precondition']['mutation_allowed'])
        self.assertEqual('nvu-ttl-hsdes', payload['request']['profile_id'])
        self.assertEqual(['new_critical_high'], payload['request']['requested_series'])
        self.assertTrue(payload['correlation_id'])
        self.assertNotIn('native_query_text', serialized_payload)
        self.assertNotIn('token', serialized_payload)

    def test_shouldRunHsdesAiWorkflowForUnsupportedSeriesAsMetricRecipeGap(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_workflow_api'),
            data=json.dumps({
                'profile_id': 'nvu-ttl-hsdes',
                'dashboard_uid': 'ip-quality-dashboard',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical'],
                'range_mode': 'ww',
                'range_start': '26WW10',
                'range_end': '26WW35',
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('needs_metric_recipe', payload['intent_validation']['status'])
        self.assertEqual(['new_critical'], payload['intent_validation']['needs_metric_recipe']['requested_series'])
        self.assertEqual('not_checked', payload['render_validation']['status'])
        self.assertEqual('not_checked', payload['gcx_precondition']['status'])
        self.assertFalse(payload['gcx_precondition']['mutation_allowed'])

    def test_shouldRunJiraAiWorkflowWithSameEnvelopeAsHsdes(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_workflow_api'),
            data=json.dumps({
                'profile_id': 'chiplet-2a-jira',
                'dashboard_uid': 'ip-quality-dashboard',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical_high'],
                'range_mode': 'ww',
                'range_start': '26WW10',
                'range_end': '26WW35',
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('jira', payload['request']['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['request']['profile_id'])
        self.assertEqual('draft_validated', payload['intent_validation']['status'])
        self.assertEqual('draft_validated', payload['render_validation']['status'])
        self.assertEqual('precondition_passed', payload['gcx_precondition']['status'])

    def test_shouldRenderAiDashboardWorkflowPage(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_workflow'))

        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI Dashboard Workflow', content)
        self.assertIn(reverse('ui_web:ai_dashboard_workflow_api'), content)
        self.assertIn('Profile', content)
        self.assertIn('chiplet-2a-jira (jira)', content)
        self.assertIn('nvu-ttl-hsdes (hsdes)', content)
        self.assertIn('Requested Series', content)
        self.assertIn('Intent Validation', content)
        self.assertIn('gcx Precondition', content)

    def test_shouldRenderJiraWorkflowResultOnPagePost(self):
        response = self.client.post(reverse('ui_web:ai_dashboard_workflow'), {
            'profile_id': 'chiplet-2a-jira',
            'dashboard_uid': 'ip-quality-dashboard',
            'chart_id': 'open_bug_trend',
            'requested_series': 'new_critical_high',
            'range_mode': 'ww',
            'range_start': '26WW10',
            'range_end': '26WW35',
            'operation': 'grafana_import',
        })

        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Provider', content)
        self.assertIn('jira', content)
        self.assertIn('chiplet-2a-jira', content)
        self.assertIn('ready_for_dry_run', content)
