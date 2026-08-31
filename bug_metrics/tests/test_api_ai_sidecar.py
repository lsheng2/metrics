from django.test import SimpleTestCase, override_settings

from bug_metrics.app.api.ai_sidecar import AiSidecarProbeService


class TestAiSidecarProbeService(SimpleTestCase):
    def test_shouldReportDisabledWithoutCallingAiBaseWhenFeatureKnobIsOff(self):
        # Given
        calls = []

        # When
        with override_settings(METRICS_AI_SIDECAR_ENABLED=False):
            status = AiSidecarProbeService(lambda url, timeout: calls.append(url)).get_status()

        # Then
        self.assertEqual('disabled', status['status'])
        self.assertFalse(status['enabled'])
        self.assertEqual([], calls)

    def test_shouldReportReadyWhenHandshakeAndRuntimeMatchExpectedDashboardProfile(self):
        # Given
        responses = {
            'http://127.0.0.1:48300/health/handshake': {
                'status': 'ok',
                'serviceId': 'dashboard-query-agent-app-service',
                'instanceToken': 'local-token',
                'handshakePath': '/health/handshake',
            },
            'http://127.0.0.1:48300/api/runtime/info': {
                'app': {
                    'profileId': 'dashboard_query_agent',
                    'capabilities': {'dashboardQuery': True, 'metricsConnector': True},
                },
            },
        }

        # When
        with override_settings(
            METRICS_AI_SIDECAR_ENABLED=True,
            METRICS_AI_BASE_URL='http://127.0.0.1:48300',
            METRICS_AI_BASE_SERVICE_ID='dashboard-query-agent-app-service',
            METRICS_AI_BASE_INSTANCE_TOKEN='local-token',
            METRICS_AI_BASE_PROFILE_ID='dashboard_query_agent',
        ):
            status = AiSidecarProbeService(lambda url, timeout: responses[url]).get_status()

        # Then
        self.assertEqual('ready', status['status'])
        self.assertEqual('dashboard_query_agent', status['profile_id'])
        self.assertEqual('dashboard-query-agent-app-service', status['service_id'])
        self.assertTrue(status['capabilities']['dashboardQuery'])

    def test_shouldReportReadyWhenDashboardCapabilityIsNestedInFeatureCapabilities(self):
        # Given
        responses = {
            'http://127.0.0.1:48300/health/handshake': {
                'status': 'ok',
                'serviceId': 'dashboard-query-agent-app-service',
                'handshakePath': '/health/handshake',
            },
            'http://127.0.0.1:48300/api/runtime/info': {
                'app': {
                    'profileId': 'dashboard_query_agent',
                    'capabilities': {
                        'featureCapabilities': {
                            'dashboardQuery': True,
                            'metricsConnector': True,
                            'grafanaOperations': True,
                        },
                    },
                },
            },
        }

        # When
        with override_settings(
            METRICS_AI_SIDECAR_ENABLED=True,
            METRICS_AI_BASE_URL='http://127.0.0.1:48300',
            METRICS_AI_BASE_SERVICE_ID='dashboard-query-agent-app-service',
            METRICS_AI_BASE_PROFILE_ID='dashboard_query_agent',
        ):
            status = AiSidecarProbeService(lambda url, timeout: responses[url]).get_status()

        # Then
        self.assertEqual('ready', status['status'])
        self.assertTrue(status['capabilities']['dashboardQuery'])
        self.assertTrue(status['capabilities']['metricsConnector'])
        self.assertTrue(status['capabilities']['grafanaOperations'])

    def test_shouldReportDegradedWhenMetricsConnectorCapabilityIsMissing(self):
        # Given
        responses = {
            'http://127.0.0.1:48300/health/handshake': {
                'status': 'ok',
                'serviceId': 'dashboard-query-agent-app-service',
                'handshakePath': '/health/handshake',
            },
            'http://127.0.0.1:48300/api/runtime/info': {
                'app': {
                    'profileId': 'dashboard_query_agent',
                    'capabilities': {
                        'featureCapabilities': {
                            'dashboardQuery': True,
                            'grafanaOperations': True,
                        },
                    },
                },
            },
        }

        # When
        with override_settings(
            METRICS_AI_SIDECAR_ENABLED=True,
            METRICS_AI_BASE_URL='http://127.0.0.1:48300',
            METRICS_AI_BASE_SERVICE_ID='dashboard-query-agent-app-service',
            METRICS_AI_BASE_PROFILE_ID='dashboard_query_agent',
        ):
            status = AiSidecarProbeService(lambda url, timeout: responses[url]).get_status()

        # Then
        self.assertEqual('degraded', status['status'])
        self.assertIn('metricsConnector', status['reason'])

    def test_shouldReportUnavailableWithoutLeakingUnexpectedHandshakePayload(self):
        # Given
        responses = {
            'http://127.0.0.1:48300/health/handshake': {
                'status': 'ok',
                'serviceId': 'wrong-service',
                'instanceToken': 'wrong-token',
                'secret': 'do-not-show',
            },
        }

        # When
        with override_settings(
            METRICS_AI_SIDECAR_ENABLED=True,
            METRICS_AI_BASE_URL='http://127.0.0.1:48300',
            METRICS_AI_BASE_SERVICE_ID='dashboard-query-agent-app-service',
            METRICS_AI_BASE_INSTANCE_TOKEN='local-token',
            METRICS_AI_BASE_PROFILE_ID='dashboard_query_agent',
        ):
            status = AiSidecarProbeService(lambda url, timeout: responses[url]).get_status()

        # Then
        self.assertEqual('unavailable', status['status'])
        self.assertIn('service identity mismatch', status['reason'])
        self.assertNotIn('do-not-show', str(status))
        self.assertNotIn('wrong-token', str(status))
