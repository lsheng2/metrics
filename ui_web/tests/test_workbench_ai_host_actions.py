from django.test import TestCase, override_settings
from django.urls import reverse

from ai_host.state import begin_stop
from ai_host.tests.test_workbench_pane import Chat, host
from ui_web.tests.workbench_view_test_support import WorkbenchViewTestSupport


class TestWorkbenchAiHostActions(WorkbenchViewTestSupport, TestCase):
    def test_bound_page_renders_same_origin_runtime_and_no_old_sync_path(self):
        scope = self._bound_scope('chiplet-2a-jira', 'jira')
        with host():
            response = self.client.get(reverse('ui_web:workbench'), {'scope_id': scope.id})
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('src="/ai/embed/session-1"', content)
        self.assertIn('"embed_host_url": "/ai/assets/embed-host-hash.js"', content)
        self.assertIn('id="workbench-ai-session-session-1"', content)
        self.assertNotIn('sync_ai_workspace', content)
        self.assertNotIn('workspaceKey', content)
        self.assertNotIn('credentialRef', content)
        self.assertNotIn('synthetic-secret', content)

    def test_timeout_keeps_page_and_chart_available(self):
        scope = self._bound_scope('chiplet-2a-jira', 'jira')
        with host(Chat.timed_out()):
            response = self.client.get(reverse('ui_web:workbench'), {'scope_id': scope.id})
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'temporarily_unavailable')
        self.assertContains(response, 'data-workbench-pane="chart"')
        self.assertNotContains(response, 'src="/ai/embed/')

    def test_shutdown_and_unconfigured_states_have_no_iframe(self):
        scope = self._bound_scope('chiplet-2a-jira', 'jira')
        with host() as handle:
            with override_settings(METRICS_AI_MODEL_NAME=''):
                unconfigured = self.client.get(reverse('ui_web:workbench'), {'scope_id': scope.id})
            begin_stop(handle)
            stopping = self.client.get(reverse('ui_web:workbench'), {'scope_id': scope.id})
        self.assertContains(unconfigured, 'not_configured')
        self.assertContains(unconfigured, 'METRICS_AI_MODEL_NAME')
        self.assertContains(stopping, 'not_running')
        self.assertNotContains(stopping, 'src="/ai/embed/')

    def test_removed_workspace_sync_post_is_not_accepted(self):
        response = self.client.post(reverse('ui_web:workbench'), {'action': 'sync_ai_workspace'})
        self.assertEqual(405, response.status_code)
