from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from ui_web.tests.workbench_browser_test_support import WorkbenchBrowserTestSupport


class TestWorkbenchAiHostActions(WorkbenchBrowserTestSupport, TestCase):
    @patch('ui_web.facades.bug_trend_facade.BugTrendFacade.get_ai_sidecar_status_payload')
    def test_shouldRenderReadyAiBasePaneWithCurrentContext(self, status_payload):
        # Given
        status_payload.return_value = {
            'status': 'ready',
            'profile_id': 'dashboard_query_agent',
            'service_id': 'dashboard-query-agent-app-service',
            'capabilities': {'dashboardQuery': True, 'metricsConnector': True},
        }

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'nvu-ttl-hsdes',
            'range_mode': 'ww',
            'begin': '26WW32',
            'end': '26WW35',
            'chart_id': 'open_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI Assistant', content)
        self.assertIn('AI Base chat side window', content)
        self.assertIn('tabindex="-1"', content)
        self.assertIn('http://127.0.0.1:48310/?embed=workbench#/chat?', content)
        self.assertIn('source=metrics-workbench', content)
        self.assertIn('workspace_key=metrics.hsdes.nvu-ttl-hsdes', content)
        self.assertIn('agent_id=dashboard_query_agent', content)
        self.assertIn('ready', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('open_bug_trend', content)

    @override_settings(METRICS_AI_BASE_EMBED_MODE='app-chat', METRICS_AI_BASE_INSTANCE_TOKEN='secret-token')
    @patch('ui_web.facades.bug_trend_facade.BugTrendFacade.get_ai_sidecar_status_payload')
    def test_shouldRenderAiBasePaneThroughAdapterWhenAppChatModeIsEnabled(self, status_payload):
        # Given
        status_payload.return_value = {
            'status': 'ready',
            'profile_id': 'dashboard_query_agent',
            'service_id': 'dashboard-query-agent-app-service',
            'capabilities': {'dashboardQuery': True, 'metricsConnector': True},
        }

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'nvu-ttl-hsdes',
            'provider_id': 'hsdes',
            'range_mode': 'ww',
            'begin': '26WW32',
            'end': '26WW35',
            'chart_id': 'open_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('http://127.0.0.1:48310/?embed=app-chat#/chat?', content)
        self.assertIn('sourceAppId=metrics-dashboard', content)
        self.assertIn('bindingKey=metrics.workbench.overview', content)
        self.assertIn('workspaceKey=metrics.hsdes.nvu-ttl-hsdes', content)
        self.assertIn('agentKey=metrics.dashboardQuery', content)
        self.assertIn('credentialRef=metrics-dashboard-local', content)
        self.assertIn('binding_request', content)
        self.assertNotIn('secret-token', content)

    @override_settings(METRICS_AI_BASE_FRONTEND_URL='http://127.0.0.1:48310')
    @patch('ui_web.facades.bug_trend_facade.BugTrendFacade.get_ai_sidecar_status_payload')
    def test_shouldHandleAiBaseOpenGrafanaChartHostActionInsideWorkbench(self, status_payload):
        # Given
        status_payload.return_value = {
            'enabled': True,
            'status': 'ready',
            'profile_id': 'dashboard_query_agent',
            'service_id': 'dashboard-query-agent-app-service',
            'capabilities': {'dashboardQuery': True, 'metricsConnector': True},
        }
        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': '7',
            'profile_id': 'chiplet-2a-jira',
            'provider_id': 'jira',
            'chart_id': 'default_bug_trend',
        })

        # When
        result = self._post_ai_base_open_grafana_host_action(response)

        # Then
        self.assertEqual('GET', result['htmx_call']['method'])
        self.assertEqual('.workbench-shell', result['htmx_call']['target'])
        self.assertIn('profile_id=chiplet-2a-jira', result['htmx_call']['url'])
        self.assertIn('provider_id=jira', result['htmx_call']['url'])
        self.assertIn('chart_id=open_bug_trend', result['htmx_call']['url'])
        self.assertEqual('handled', result['ack']['status'])
        self.assertEqual('metrics-workbench.chart', result['ack']['result']['openedIn'])
