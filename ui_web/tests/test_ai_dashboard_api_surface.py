import json
from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from bug_metrics.app.api import DashboardAiPublishApprovalRequest, DashboardCompositionIntent, bug_trend_api
from bug_metrics.models import BugTrendAuditEvent, JiraScopeConfig
from jira_history.models import JiraIssue


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
        self._seed_jira_aggregate_for_publish()
        approval = self._approved_publish_request()
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
                    'visualization': 'barchart',
                    'approval_id': approval['approval_id'],
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
        self.assertEqual('published', payload['approval']['status'])
        self.assertEqual('jira', payload['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['profile_id'])
        self.assertEqual('open_bug_trend', payload['chart_id'])
        self.assertEqual(1, payload['chart_version'])
        self.assertEqual(['new_critical_high'], payload['requested_series'])
        self.assertEqual('barchart', payload['visualization'])
        self.assertEqual('dryrun-local-demo', event.request_summary['dry_run_proof_id'])
        self.assertEqual('ai-open-bug-trend-demo', imported_dashboard['uid'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockJiraAiDashboardPublishWhenAggregateRowsAreMissing(self):
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
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
                    'approval_id': 'approval_chat_demo_missing_data',
                    'dry_run_proof_id': 'dryrun-local-demo',
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('data_not_ready', payload['reason'])
        self.assertEqual('unavailable', payload['readiness']['status'])
        self.assertFalse(importer.called)
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_callback_recorded').exists())

    def test_shouldTrackAiGrafanaPublishApprovalStateTransitions(self):
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-local-demo',
                actor='ai_sidecar',
            )
        )

        approved = bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')
        rejected_seed = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo-rejected',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-rejected-demo',
                actor='ai_sidecar',
            )
        )
        rejected = bug_trend_api.decide_ai_grafana_publish_approval(rejected_seed['approval_id'], 'rejected', 'local_operator')

        self.assertEqual('pending_approval', pending['status'])
        self.assertEqual('approved', approved['status'])
        self.assertEqual('rejected', rejected['status'])
        self.assertEqual('approved', bug_trend_api.get_ai_grafana_publish_approval(pending['approval_id'])['status'])

    def test_shouldExposeAiGrafanaPublishApprovalApi(self):
        create_response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_approval_api'),
            data=json.dumps({
                'profile_id': 'chiplet-2a-jira',
                'dashboard_uid': 'ai-open-bug-trend-demo',
                'chart_id': 'open_bug_trend',
                'requested_series': ['new_critical_high'],
                'range_mode': 'ww',
                'range_start': '26WW32',
                'range_end': '26WW35',
                'dry_run_proof_id': 'dryrun-local-demo',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        approval_id = create_response.json()['approval_id']
        decide_response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_approval_decision_api'),
            data=json.dumps({
                'approval_id': approval_id,
                'decision': 'approved',
                'actor': 'local_operator',
            }),
            content_type='application/json',
        )
        state_response = self.client.get(reverse('ui_web:ai_dashboard_publish_approval_api'), {'approval_id': approval_id})

        self.assertEqual(200, create_response.status_code)
        self.assertEqual('pending_approval', create_response.json()['status'])
        self.assertEqual(200, decide_response.status_code)
        self.assertEqual('approved', decide_response.json()['status'])
        self.assertEqual(200, state_response.status_code)
        self.assertEqual('approved', state_response.json()['status'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockAiDashboardPublishWhenApprovalIsNotApproved(self):
        self._seed_jira_aggregate_for_publish()
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-local-demo',
                actor='ai_sidecar',
            )
        )
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
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
                    'approval_id': pending['approval_id'],
                    'dry_run_proof_id': 'dryrun-local-demo',
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('approval_not_granted', payload['reason'])
        self.assertEqual('pending_approval', payload['approval']['status'])
        self.assertFalse(importer.called)

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldListAiGrafanaPublishHistoryWithLatestMarker(self):
        self._seed_jira_aggregate_for_publish()
        first = self._publish_jira_demo('first-proof', '2026-08-03T00:00:00')
        second = self._publish_jira_demo('second-proof', '2026-08-10T00:00:00')

        response = self.client.get(reverse('ui_web:ai_dashboard_publish_history_api'))

        payload = response.json()
        rows = payload['items']
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(second['approval']['approval_id'], rows[0]['approval_id'])
        self.assertEqual(first['approval']['approval_id'], rows[1]['approval_id'])
        self.assertTrue(rows[0]['latest'])
        self.assertFalse(rows[1]['latest'])
        self.assertEqual('jira', rows[0]['provider_id'])
        self.assertEqual('chiplet-2a-jira', rows[0]['profile_id'])
        self.assertEqual('open_bug_trend', rows[0]['chart_id'])
        self.assertIn('/d/ai-open-bug-trend-demo/', rows[0]['dashboard_url'])

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

    def test_shouldExposeMetricsWorkspaceContextBundleWithCanonicalDataBlocks(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_workspace_context_api'), {
            'profile_id': 'nvu-ttl-hsdes',
        })

        payload = response.json()
        serialized_payload = json.dumps(payload).lower()
        files_by_path = {item['path']: item for item in payload['files']}
        data_block_catalog = files_by_path['metrics-context/data-block-catalog.json']['content_json']
        quality_facts = data_block_catalog['data_blocks'][0]
        self.assertEqual(200, response.status_code)
        self.assertEqual('metrics.workspace_context_bundle', payload['bundle_type'])
        self.assertEqual('metrics-dashboard', payload['source_app_id'])
        self.assertEqual('metrics.hsdes.nvu-ttl-hsdes', payload['workspace_key'])
        self.assertEqual('Metrics hsdes nvu-ttl-hsdes', payload['workspace_name'])
        self.assertEqual('hsdes', payload['boundary']['allowed_provider_ids'][0])
        self.assertEqual('nvu-ttl-hsdes', payload['boundary']['allowed_profile_ids'][0])
        self.assertIn('metrics-context/workspace-boundary.json', files_by_path)
        self.assertIn('metrics-context/canonical-field-map.json', files_by_path)
        self.assertIn('metrics-context/data-block-catalog.json', files_by_path)
        self.assertEqual('model_context', files_by_path['metrics-context/data-block-catalog.json']['visibility'])
        self.assertEqual('data_block_catalog', files_by_path['metrics-context/data-block-catalog.json']['role'])
        self.assertEqual('catalog_only', files_by_path['metrics-context/grafana-render-contract.json']['visibility'])
        self.assertEqual('work_item.quality_facts', quality_facts['block_id'])
        self.assertIn('severity', quality_facts['canonical_fields'])
        self.assertIn('component', quality_facts['canonical_fields'])
        self.assertIn('created_at', quality_facts['canonical_fields'])
        self.assertIn('filter', quality_facts['allowed_transforms'])
        self.assertNotIn('native_query_text', serialized_payload)
        self.assertNotIn('password', serialized_payload)
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

    def test_shouldRunRecipeDrivenWorkflowForTotalBugTrend(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_workflow_api'),
            data=json.dumps({
                'profile_id': 'nvu-ttl-hsdes',
                'dashboard_uid': 'ip-quality-dashboard',
                'chart_id': 'total_bug_trend',
                'requested_series': ['total_open_bugs'],
                'range_mode': 'ww',
                'range_start': '26WW32',
                'range_end': '26WW35',
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
            }),
            content_type='application/json',
        )

        payload = response.json()
        panel = payload['intent_validation']['draft_render_config']['sections'][0]['panels'][0]
        self.assertEqual(200, response.status_code)
        self.assertEqual('draft_validated', payload['intent_validation']['status'])
        self.assertEqual('total_bug_trend', payload['request']['chart_id'])
        self.assertEqual({'chart_id': 'total_bug_trend', 'chart_version': 1}, panel['chart_recipe_ref'])
        self.assertEqual(['total_open_bugs'], panel['value_fields'])

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
        self.assertIn('Recent AI Grafana Publishes', content)

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

    def _seed_jira_aggregate_for_publish(self):
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open', 'In Progress', 'Reopened'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            milestone_field='2a',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Open stopper bug',
            issue_type='Bug',
            status='Open',
            severity_value='P1-Stopper',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            summary='Open high bug',
            issue_type='Bug',
            status='Open',
            severity_value='P2-High',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        )
        return bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 30))

    def _approved_publish_request(self):
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-local-demo',
                actor='ai_sidecar',
            )
        )
        return bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')

    def _publish_jira_demo(self, proof_id, from_time):
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id=proof_id,
                actor='ai_sidecar',
            )
        )
        approval = bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')
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
                    'visualization': 'barchart',
                    'approval_id': approval['approval_id'],
                    'dry_run_proof_id': proof_id,
                    'correlation_id': f'corr-{proof_id}',
                }),
                content_type='application/json',
                HTTP_X_TEST_FROM_TIME=from_time,
            )
        payload = response.json()
        self.assertEqual('published', payload['status'])
        return payload
