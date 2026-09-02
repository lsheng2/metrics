import json

from django.test import TestCase
from django.urls import reverse

from bug_metrics.app.api import DashboardCompositionIntent, bug_trend_api


class TestAiDashboardApiSurface(TestCase):
    def test_shouldExposeAiDashboardConnectorIdentity(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_identity_api'))

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertEqual('metrics-dashboard-service', payload['serviceId'])
        self.assertTrue(payload['capabilities']['dashboardQuery'])
        self.assertTrue(payload['capabilities']['metricsConnector'])
        self.assertTrue(payload['capabilities']['grafanaOperations'])

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

    def test_shouldAcceptAiDashboardCatalogConnectorBoundaryParams(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_catalog_api'), {
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
            'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
        })

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('nvu-ttl-hsdes', payload['profiles'][0]['profile_id'])

    def test_shouldRejectAiDashboardCatalogWhenBoundaryParamsMismatchProfile(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_catalog_api'), {
            'provider_id': 'jira',
            'profile_id': 'nvu-ttl-hsdes',
            'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
        })

        self.assertEqual(400, response.status_code)
        self.assertEqual('provider_id does not match the profile boundary.', response.json()['error'])

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

    def test_shouldValidateAiWorkspaceArtifactWithMetadata(self):
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
            reverse('ui_web:ai_dashboard_artifact_validation_api'),
            data=json.dumps({
                'artifact_ref': 'ai-base-artifact://workspace/art_123',
                'artifact_version': 1,
                'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
                'correlation_id': 'corr-artifact-1',
                'artifact': {
                    'profile_id': 'nvu-ttl-hsdes',
                    'dashboard_uid': 'ip-quality-dashboard',
                    'chart_id': 'open_bug_trend',
                    'requested_series': ['new_critical_high'],
                    'range_mode': 'ww',
                    'range_start': '26WW10',
                    'range_end': '26WW35',
                    'draft_render_config': draft,
                },
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('draft_validated', payload['status'])
        self.assertTrue(payload['valid'])
        self.assertEqual('ai-base-artifact://workspace/art_123', payload['artifact_ref'])
        self.assertEqual(1, payload['artifact_version'])
        self.assertEqual('metrics.hsdes.nvu-ttl-hsdes', payload['workspace_key'])
        self.assertEqual('corr-artifact-1', payload['correlation_id'])
        self.assertEqual('draft_validated', payload['render_validation']['status'])
        self.assertIn('normalized_render_config', payload)

    def test_shouldRejectAiWorkspaceArtifactWhenWorkspaceKeyDoesNotMatchProfile(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_artifact_validation_api'),
            data=json.dumps({
                'artifact_ref': 'ai-base-artifact://workspace/art_cross_profile',
                'artifact_version': 1,
                'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
                'correlation_id': 'corr-artifact-cross-profile',
                'artifact': {
                    'profile_id': 'chiplet-2a-jira',
                    'dashboard_uid': 'ip-quality-dashboard',
                    'chart_id': 'open_bug_trend',
                    'requested_series': ['new_critical_high'],
                    'range_mode': 'ww',
                    'range_start': '26WW32',
                    'range_end': '26WW35',
                },
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('validation_failed', payload['status'])
        self.assertFalse(payload['valid'])
        self.assertIn('workspace_boundary_mismatch', {item['code'] for item in payload['findings']})

    def test_shouldBlockAiWorkspaceArtifactWithUnsupportedSeries(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_artifact_validation_api'),
            data=json.dumps({
                'artifact_ref': 'ai-base-artifact://workspace/art_bad',
                'artifact_version': 1,
                'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
                'correlation_id': 'corr-artifact-bad',
                'artifact': {
                    'profile_id': 'nvu-ttl-hsdes',
                    'dashboard_uid': 'ip-quality-dashboard',
                    'chart_id': 'open_bug_trend',
                    'requested_series': ['new_critical'],
                    'range_mode': 'ww',
                    'range_start': '26WW10',
                    'range_end': '26WW35',
                },
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('needs_metric_recipe', payload['status'])
        self.assertFalse(payload['valid'])
        self.assertEqual(['new_critical'], payload['intent_validation']['needs_metric_recipe']['requested_series'])
        self.assertNotIn('normalized_render_config', payload)

    def test_shouldRejectAiWorkspaceArtifactWithUnsafeContent(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_artifact_validation_api'),
            data=json.dumps({
                'artifact_ref': 'ai-base-artifact://workspace/art_unsafe',
                'artifact_version': 1,
                'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
                'correlation_id': 'corr-artifact-unsafe',
                'artifact': {
                    'profile_id': 'nvu-ttl-hsdes',
                    'dashboard_uid': 'ip-quality-dashboard',
                    'chart_id': 'open_bug_trend',
                    'requested_series': ['new_critical_high'],
                    'range_mode': 'ww',
                    'range_start': '26WW10',
                    'range_end': '26WW35',
                    'privatePath': 'D:/private/path',
                    'providerNativeQuery': 'select * from private_table',
                },
            }),
            content_type='application/json',
        )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('validation_failed', payload['status'])
        self.assertFalse(payload['valid'])
        self.assertIn('unsafe_artifact_content', {item['code'] for item in payload['findings']})
        self.assertNotIn('D:/private/path', json.dumps(payload))

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

    def test_shouldExposeSafeEvidenceContextForAiBase(self):
        response = self.client.get(reverse('ui_web:ai_dashboard_context_api'), {
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
            'workspace_key': 'metrics.hsdes.nvu-ttl-hsdes',
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
