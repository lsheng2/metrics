from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import ProviderProfileConfig
from ui_web.tests.provider_setup_view_test_support import ProviderSetupViewTestSupport


class TestProviderSetupConnections(ProviderSetupViewTestSupport, TestCase):
    @patch('bug_metrics.app.api.provider_profile_connection_test.Jira')
    def test_shouldTestProviderProfileConnectionWithoutSavingProfile(self, create_jira_client):
        # Given
        create_jira_client.return_value.get_server_info.return_value = {
            'serverTitle': 'Jira Test',
            'version': '10.0',
        }
        payload = self._profile_payload()
        payload['action'] = 'test_connection'
        payload['profile_id'] = 'transient-connection-profile'
        payload['connection_base_url'] = 'https://jira.profile.example'
        payload['connection_auth_mode'] = 'server_pat'
        payload['credential_ref'] = 'profile:local'
        payload['connection_api_token'] = 'secret-token'

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Connection test: success', content)
        self.assertIn('Jira connection succeeded.', content)
        self.assertIn('provider-connection-test-result', content)
        self.assertIn('Last test: success', content)
        self.assertNotIn('secret-token', content)
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='transient-connection-profile').exists())
        result_layout = self._measure_connection_test_result_layout(content)
        self.assertTrue(result_layout['result_visible'])
        self.assertTrue(result_layout['result_before_actions'])
        self.assertIn('Jira connection succeeded.', result_layout['result_text'])

    @patch('bug_metrics.app.api.provider_profile_connection_test.HsdesHttpClient')
    def test_shouldTestHsdesConnectionWithVisibleProbeFields(self, hsdes_client):
        # Given
        hsdes_client.return_value.execute_saved_query.return_value = {'total': 1, 'data': [{'id': '1'}]}
        payload = self._hsdes_profile_payload()
        payload['action'] = 'test_connection'
        payload['hsdes_saved_query_id'] = '15017652869'
        payload['hsdes_tenant'] = 'ip_fw_sw_sensing.tenant'
        payload['hsdes_subject'] = 'ip_fw_sw_sensing.bug'

        # When
        response = self.client.post(reverse('ui_web:provider_setup'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('HSD-ES Connection Probe', content)
        self.assertIn('value="15017652869"', content)
        self.assertIn('value="ip_fw_sw_sensing.tenant"', content)
        self.assertIn('value="ip_fw_sw_sensing.bug"', content)
        self.assertIn('Connection test: success', content)
        self.assertIn('HSD-ES saved-query probe succeeded.', content)
        self.assertNotIn('Advanced source settings', content)
        hsdes_client.return_value.execute_saved_query.assert_called_once_with(
            '15017652869', 'ip_fw_sw_sensing.tenant', 'ip_fw_sw_sensing.bug', ['id'], 0, 1,
        )
