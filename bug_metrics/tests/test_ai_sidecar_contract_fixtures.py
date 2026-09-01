import json
from pathlib import Path

from django.test import TestCase
from django.urls import reverse


class TestAiSidecarContractFixtures(TestCase):
    def test_shouldPublishDashboardAiBaseProfileSuggestion(self):
        fixture_path = Path('openspec/changes/archive/2026-09-01-enable-dashboard-ai-sidecar-platform-contract/contracts/ai-base-dashboard-profile-suggestion.json')

        payload = json.loads(fixture_path.read_text(encoding='utf-8'))
        self.assertEqual('dashboard_query_agent', payload['profile_id'])
        self.assertEqual('dashboard-query-agent-app-service', payload['service_id'])
        self.assertEqual({'dashboardQuery', 'metricsConnector', 'grafanaOperations'}, set(payload['feature_gates']))
        self.assertEqual(['dashboard_query_agent'], payload['metrics_connector']['profile_scope']['allowlist'])
        self.assertEqual({'sample_agent', 'report_creator', 'soc_ai_driver'}, set(payload['metrics_connector']['profile_scope']['blocked_profiles']))
        self.assertFalse(payload['gcx_tools']['raw_shell_allowed'])
        self.assertFalse(payload['gcx_tools']['raw_gcx_api_passthrough_allowed'])

    def test_shouldPublishMetricsConnectorOperationFixtureForAiBase(self):
        fixture_path = Path('openspec/changes/archive/2026-09-01-enable-dashboard-ai-sidecar-platform-contract/contracts/metrics-connector-operations.json')

        payload = json.loads(fixture_path.read_text(encoding='utf-8'))
        operation_ids = {operation['operation_id'] for operation in payload['operations']}
        serialized_operations = json.dumps(payload['operations']).lower()
        self.assertEqual('metrics-dashboard', payload['connector_id'])
        self.assertEqual('0.2', payload['metrics_contract_version'])
        self.assertEqual({
            'catalog.lookup',
            'workflow.run',
            'workflow.publish_demo',
            'intent.validate',
            'render_config.validate',
            'gcx.precondition',
            'gcx.publication_callback',
            'context.lookup',
        }, operation_ids)
        self.assertEqual(reverse('ui_web:ai_dashboard_catalog_api'), self._operation_path(payload, 'catalog.lookup'))
        self.assertEqual(reverse('ui_web:ai_dashboard_workflow_api'), self._operation_path(payload, 'workflow.run'))
        self.assertEqual(reverse('ui_web:ai_dashboard_publish_demo_api'), self._operation_path(payload, 'workflow.publish_demo'))
        self.assertEqual(reverse('ui_web:ai_dashboard_intent_validation_api'), self._operation_path(payload, 'intent.validate'))
        self.assertEqual(reverse('ui_web:ai_dashboard_render_config_validation_api'), self._operation_path(payload, 'render_config.validate'))
        self.assertEqual(reverse('ui_web:ai_dashboard_gcx_precondition_api'), self._operation_path(payload, 'gcx.precondition'))
        self.assertEqual(reverse('ui_web:ai_dashboard_gcx_publication_callback_api'), self._operation_path(payload, 'gcx.publication_callback'))
        self.assertEqual(reverse('ui_web:ai_dashboard_context_api'), self._operation_path(payload, 'context.lookup'))
        self.assertTrue(all('response_example' in operation for operation in payload['operations']))
        self.assertNotIn('native_query_text', serialized_operations)
        self.assertNotIn('password', serialized_operations)
        self.assertNotIn('token', serialized_operations)
        self.assertNotIn('api_key', serialized_operations)

    def _operation_path(self, payload, operation_id):
        for operation in payload['operations']:
            if operation['operation_id'] == operation_id:
                return operation['path']
        return ''
