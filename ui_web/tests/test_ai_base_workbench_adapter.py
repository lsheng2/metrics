from pathlib import Path

from django.test import TestCase, override_settings

from ui_web.ai_base_workbench_adapter import AiBaseWorkbenchAdapter
from ui_web.workbench_state import WorkbenchPageQueryState


class TestAiBaseWorkbenchAdapter(TestCase):
    def setUp(self):
        self.adapter = AiBaseWorkbenchAdapter('scripts\\e2e_dashboard_ai_stack.ps1 -Action restart -ForceByPort')
        self.state = WorkbenchPageQueryState(
            profile_id='nvu-ttl-hsdes',
            provider_id='hsdes',
            range_mode='ww',
            begin='26WW32',
            end='26WW35',
            chart_id='open_bug_trend',
            chart_version='1',
            calculation_run_id='run-1',
            selected_bucket_id='2026-08-21',
            selected_series_name='new_critical_high',
        )

    def test_shouldBuildStandaloneContextWithoutRequiringAiRuntime(self):
        payload = self.adapter.context(self.state, {'status': 'disabled', 'enabled': False})

        self.assertEqual('nvu-ttl-hsdes', payload['profile_id'])
        self.assertFalse(payload['ai_base']['enabled'])
        self.assertEqual('disabled', payload['ai_base']['status'])
        self.assertEqual('metrics.hsdes.nvu-ttl-hsdes', payload['ai_base']['workspace_key'])
        self.assertIn('e2e_dashboard_ai_stack.ps1', payload['ai_base']['launcher_command'])

    @override_settings(METRICS_AI_BASE_FRONTEND_URL='http://127.0.0.1:48310', METRICS_AI_BASE_EMBED_MODE='workbench')
    def test_shouldBuildLegacyCompactEmbedUrlByDefault(self):
        url = self.adapter.chat_url(self.state, {'profile_id': 'dashboard_query_agent'})

        self.assertIn('http://127.0.0.1:48310/?embed=workbench#/chat?', url)
        self.assertIn('source=metrics-workbench', url)
        self.assertIn('workspace_key=metrics.hsdes.nvu-ttl-hsdes', url)
        self.assertIn('agent_id=dashboard_query_agent', url)

    @override_settings(
        METRICS_AI_BASE_FRONTEND_URL='http://127.0.0.1:48310',
        METRICS_AI_BASE_EMBED_MODE='app-chat',
        METRICS_AI_BASE_INSTANCE_TOKEN='secret-token',
    )
    def test_shouldBuildGenericAppChatUrlWithoutLeakingInstanceToken(self):
        payload = self.adapter.context(self.state, {'profile_id': 'dashboard_query_agent'})
        url = payload['ai_base']['chat_url']

        self.assertIn('http://127.0.0.1:48310/?embed=app-chat#/chat?', url)
        self.assertIn('sourceAppId=metrics-dashboard', url)
        self.assertIn('bindingKey=metrics.workbench.overview', url)
        self.assertIn('workspaceKey=metrics.hsdes.nvu-ttl-hsdes', url)
        self.assertIn('agentKey=metrics.dashboardQuery', url)
        self.assertIn('credentialRef=metrics-dashboard-local', url)
        self.assertNotIn('secret-token', url)
        self.assertEqual('metrics.dashboardQuery', payload['ai_base']['binding_request']['agentKey'])
        self.assertEqual('metrics.workbench.nvu-ttl-hsdes.overview', payload['ai_base']['binding_request']['sessionKey'])

    def test_shouldKeepAiBaseCouplingOutOfCoreWorkbenchModules(self):
        guarded_paths = [
            'ui_web/workbench_state.py',
            'ui_web/workbench_grafana.py',
            'ui_web/workbench_registry.py',
            'bug_metrics/app/api/provider_aggregates.py',
            'bug_metrics/app/api/provider_profiles.py',
        ]

        for relative_path in guarded_paths:
            content = self._repo_file(relative_path)
            self.assertNotIn('ai_base_workbench_adapter', content, relative_path)
            self.assertNotIn('AppChatBinding', content, relative_path)
            self.assertNotIn('sourceAppId', content, relative_path)

    def _repo_file(self, relative_path):
        return (Path(__file__).resolve().parents[2] / relative_path).read_text(encoding='utf-8')
