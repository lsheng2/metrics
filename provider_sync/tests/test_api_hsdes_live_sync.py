import base64
import json
import urllib.error
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService
from provider_sync.app.api.hsdes import HsdesHttpClient, HsdesProviderError, HsdesSavedQueryAdapter, HsdesSavedQuerySyncService
from provider_sync.models import ProviderSyncCursor


class FakeHsdesClient:
    def __init__(self, pages=None, error=None):
        self.pages = pages or []
        self.error = error
        self.requests = []

    def execute_saved_query(self, query_id, tenant, subject, field_names, start_at, max_results):
        self.requests.append({
            'query_id': query_id,
            'tenant': tenant,
            'subject': subject,
            'field_names': field_names,
            'start_at': start_at,
            'max_results': max_results,
        })
        if self.error:
            raise self.error
        return self.pages[len(self.requests) - 1]


class TestHsdesLiveSync(TestCase):
    def test_shouldBuildHsdesHttpSavedQueryRequestWithConfiguredAuthSurface(self):
        # Given
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeHttpResponse({'data': [], 'total': 0})

        client = HsdesHttpClient(
            base_url='https://hsdes-api.intel.com/rest',
            auth_mode='token',
            token='secret-token',
            timeout_seconds=15,
            opener=fake_urlopen,
        )

        # When
        page = client.execute_saved_query(
            query_id='15017652869',
            tenant='ip_fw_sw_sensing.tenant',
            subject='ip_fw_sw_sensing.bug',
            field_names=['id', 'HSD_type'],
            start_at=0,
            max_results=100,
        )

        # Then
        self.assertEqual({'data': [], 'total': 0}, page)
        request, timeout = requests[0]
        self.assertEqual(15, timeout)
        self.assertIn('/rest/auth/query/execution/15017652869?', request.full_url)
        self.assertIn('start_at=0', request.full_url)
        self.assertIn('max_results=100', request.full_url)
        self.assertIn('tenant=ip_fw_sw_sensing.tenant', request.full_url)
        self.assertIn('subject=ip_fw_sw_sensing.bug', request.full_url)
        self.assertEqual('Bearer secret-token', request.headers['Authorization'])

    def test_shouldUsePowerShellDefaultCredentialsForWindowsIntegratedAuthTransport(self):
        # Given
        calls = []

        def fake_runner(command, capture_output, text, timeout, env):
            calls.append({
                'command': command,
                'capture_output': capture_output,
                'text': text,
                'timeout': timeout,
                'url': command[-2],
            })
            return FakeProcess(stdout=json.dumps({'data': [{'id': '16000000001'}], 'total': 1}), stderr='', returncode=0)

        client = HsdesHttpClient(
            base_url='https://hsdes-api.intel.com/rest',
            auth_mode='kerberos',
            timeout_seconds=15,
            transport='powershell',
            powershell_runner=fake_runner,
        )

        # When
        page = client.execute_saved_query('15017652869', 'tenant', 'subject', ['id'], 0, 1)

        # Then
        self.assertEqual(1, page['total'])
        decoded_script = base64.b64decode(calls[0]['command'][-1]).decode('utf-16le')
        self.assertIn('-EncodedCommand', calls[0]['command'])
        self.assertIn('-UseDefaultCredentials', decoded_script)
        self.assertIn('/rest/query/execution/15017652869?', decoded_script)

    def test_shouldNormalizeHsdesHttpErrorsIntoSafeCategories(self):
        # Given / When / Then
        self.assertEqual('auth_failed', self._http_error_category_for_status(401))
        self.assertEqual('permission_denied', self._http_error_category_for_status(403))
        self.assertEqual('rate_limited', self._http_error_category_for_status(429))
        self.assertEqual('provider_error', self._http_error_category_for_status(500))

    def test_shouldRejectMalformedHsdesHttpPayload(self):
        # Given
        client = HsdesHttpClient(
            base_url='https://hsdes-api.intel.com/rest',
            transport='urllib',
            opener=lambda request, timeout: FakeHttpResponse(['not-a-dict']),
        )

        # When / Then
        with self.assertRaises(HsdesProviderError) as context:
            client.execute_saved_query('15017652869', 'tenant', 'subject', ['id'], 0, 100)
        self.assertEqual('malformed_payload', context.exception.category)

    def test_shouldFetchHsdesSavedQueryPagesThroughAdapter(self):
        # Given
        client = FakeHsdesClient([
            {
                'data': [
                    {'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug'}},
                    {'id': '16000000002', 'rev': '1', 'fieldValues': {'HSD_type': 'bug'}},
                ],
                'start_at': 0,
                'max_results': 2,
                'total': 3,
            },
            {
                'data': [
                    {'id': '16000000003', 'rev': '1', 'fieldValues': {'HSD_type': 'bug'}},
                ],
                'start_at': 2,
                'max_results': 2,
                'total': 3,
            },
        ])
        adapter = HsdesSavedQueryAdapter(client, page_size=2)

        # When
        payload = adapter.fetch_saved_query(
            query_id='15017652869',
            tenant='ip_fw_sw_sensing.tenant',
            subject='ip_fw_sw_sensing.bug',
            field_names=['id', 'HSD_type'],
        )

        # Then
        self.assertEqual(3, len(payload['articles']))
        self.assertEqual([0, 2], [request['start_at'] for request in client.requests])
        self.assertEqual('15017652869', client.requests[0]['query_id'])
        self.assertEqual([], payload['errors'])

    def test_shouldRejectPartialHsdesSavedQueryPayload(self):
        # Given
        client = FakeHsdesClient([
            {
                'data': [{'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug'}}],
                'errors': [{'message': 'partial response'}],
                'total': 2,
            },
        ])
        adapter = HsdesSavedQueryAdapter(client, page_size=2)

        # When / Then
        with self.assertRaises(HsdesProviderError) as context:
            adapter.fetch_saved_query(
                query_id='15017652869',
                tenant='ip_fw_sw_sensing.tenant',
                subject='ip_fw_sw_sensing.bug',
                field_names=['id', 'HSD_type'],
            )
        self.assertEqual('partial_response', context.exception.category)

    def test_shouldRejectShortHsdesSavedQueryPaginationWithoutFinalPage(self):
        # Given
        client = FakeHsdesClient([{
            'data': [],
            'total': 2,
        }])
        adapter = HsdesSavedQueryAdapter(client, page_size=2)

        # When / Then
        with self.assertRaises(HsdesProviderError) as context:
            adapter.fetch_saved_query(
                query_id='15017652869',
                tenant='ip_fw_sw_sensing.tenant',
                subject='ip_fw_sw_sensing.bug',
                field_names=['id', 'HSD_type'],
            )
        self.assertEqual('partial_response', context.exception.category)

    @override_settings(METRICS_PROVIDER_CACHE_ENABLED=True)
    def test_shouldReturnRunningWithoutSecondExternalFetchWhenSameRefreshIsInFlight(self):
        # Given
        cache_service = ProviderSyncCacheService()
        cache_service.mark_running('hsdes', 'nvu-ttl-hsdes', '15017652869')
        client = FakeHsdesClient([{
            'data': [{'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug'}}],
            'total': 1,
        }])
        sync_service = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(client),
            cache_service=cache_service,
        )

        # When
        result = sync_service.sync_nvu_ttl_profile(begin_ww='26WW32', end_ww='26WW32')

        # Then
        self.assertEqual('running', result['status'])
        self.assertEqual(0, len(client.requests))

    def test_shouldSyncHsdesSavedQueryIntoGenericCacheAndGenerateQualityArtifacts(self):
        # Given
        client = FakeHsdesClient([
            {
                'data': [
                    {'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'fwsw', 'submitted_date': '2026-08-04T08:00:00Z'}},
                    {'id': '16000000002', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'media', 'submitted_date': '2026-08-05T08:00:00Z'}},
                    {'id': '16000000002', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'media', 'submitted_date': '2026-08-05T08:00:00Z'}},
                ],
                'start_at': 0,
                'max_results': 100,
                'total': 3,
            },
        ])
        sync_service = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(client),
            cache_service=ProviderSyncCacheService(),
        )

        # When
        result = sync_service.sync_nvu_ttl_profile(begin_ww='26WW32', end_ww='26WW32')

        # Then
        self.assertEqual('success', result['status'])
        self.assertEqual(2, result['fact_count'])
        artifact = ProviderSyncCacheService().latest_aggregate_artifact(
            'hsdes',
            'nvu-ttl-hsdes',
            'component_bug',
            1,
            '26WW32',
            '26WW32',
        )
        self.assertEqual(ProviderFreshnessStatus.LIVE_SYNCED, artifact.run_metadata_json['freshness_status'])
        self.assertEqual(1, self._component_count(artifact, 'fwsw'))
        self.assertEqual(1, self._component_count(artifact, 'media'))

    def test_shouldRecordFailureWithoutDeletingLastSuccessfulHsdesArtifact(self):
        # Given
        cache_service = ProviderSyncCacheService()
        successful_sync = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(FakeHsdesClient([{
                'data': [{'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'fwsw', 'submitted_date': '2026-08-04T08:00:00Z'}}],
                'start_at': 0,
                'max_results': 100,
                'total': 1,
            }])),
            cache_service=cache_service,
        )
        successful_sync.sync_nvu_ttl_profile(begin_ww='26WW32', end_ww='26WW32')
        failing_sync = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(FakeHsdesClient(error=HsdesProviderError('auth_failed', 'redacted auth failure'))),
            cache_service=cache_service,
        )

        # When
        result = failing_sync.sync_nvu_ttl_profile(begin_ww='26WW32', end_ww='26WW32')

        # Then
        cursor = ProviderSyncCursor.objects.get(provider_id='hsdes', profile_id='nvu-ttl-hsdes')
        artifact = cache_service.latest_aggregate_artifact('hsdes', 'nvu-ttl-hsdes', 'component_bug', 1, '26WW32', '26WW32')
        self.assertEqual('failed', result['status'])
        self.assertEqual(ProviderSyncCursor.STATUS_FAILED, cursor.status)
        self.assertEqual('auth_failed', cursor.error_category)
        self.assertEqual(1, self._component_count(artifact, 'fwsw'))

    @override_settings(METRICS_HSDES_LIVE_SYNC_ENABLED=False)
    def test_shouldSkipLiveHsdesSmokeCommandWhenNotExplicitlyConfigured(self):
        # Given
        output = JsonOutput()

        # When
        call_command('sync_hsdes_profile', '--begin-ww', '26WW32', '--end-ww', '26WW32', stdout=output)

        # Then
        payload = json.loads(output.value)
        self.assertEqual('skipped', payload['status'])
        self.assertEqual('configuration_required', payload['freshness_status'])
        self.assertIn('METRICS_HSDES_LIVE_SYNC_ENABLED', payload['reason'])

    @override_settings(METRICS_HSDES_LIVE_SYNC_ENABLED=True)
    def test_shouldSyncHsdesSavedQueryThroughGenericProviderProfileCommand(self):
        # Given
        output = JsonOutput()
        fake_client = FakeHsdesClient([{
            'data': [
                {'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'fwsw', 'submitted_date': '2026-08-04T08:00:00Z'}},
            ],
            'total': 1,
        }])

        # When
        with patch('provider_sync.management.commands.sync_provider_profile.HsdesHttpClient', return_value=fake_client):
            call_command(
                'sync_provider_profile',
                '--profile-id',
                'nvu-ttl-hsdes',
                '--begin-ww',
                '26WW32',
                '--end-ww',
                '26WW32',
                stdout=output,
            )

        # Then
        payload = json.loads(output.value)
        self.assertEqual('success', payload['status'])
        self.assertEqual('nvu-ttl-hsdes', payload['profile_id'])
        self.assertEqual('15017652869', fake_client.requests[0]['query_id'])
        self.assertEqual('ip_fw_sw_sensing.tenant', fake_client.requests[0]['tenant'])
        self.assertEqual('ip_fw_sw_sensing.bug', fake_client.requests[0]['subject'])

    def test_shouldReturnSafeUnsupportedResultForGenericSyncUnknownProfile(self):
        # Given
        output = JsonOutput()

        # When
        call_command(
            'sync_provider_profile',
            '--profile-id',
            'missing-profile',
            '--begin-ww',
            '26WW32',
            '--end-ww',
            '26WW32',
            stdout=output,
        )

        # Then
        payload = json.loads(output.value)
        self.assertEqual('unsupported', payload['status'])
        self.assertEqual('missing-profile', payload['profile_id'])
        self.assertEqual('profile_not_found', payload['blockers'][0]['code'])

    def test_shouldGenerateAllFirstWaveHsdesQualityArtifactsFromLiveFacts(self):
        # Given
        client = FakeHsdesClient([{
            'data': [
                {'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'priority': 'high', 'component': 'fwsw', 'status': 'open', 'submitted_date': '2026-08-04T08:00:00Z'}},
                {'id': '16000000002', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'priority': 'medium', 'component': 'media', 'status': 'closed', 'submitted_date': '2026-08-05T08:00:00Z', 'closed_date': '2026-08-07T08:00:00Z'}},
            ],
            'total': 2,
        }])
        cache_service = ProviderSyncCacheService()
        sync_service = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(client),
            cache_service=cache_service,
        )

        # When
        result = sync_service.sync_nvu_ttl_profile(begin_ww='26WW32', end_ww='26WW32')

        # Then
        self.assertEqual('success', result['status'])
        self.assertEqual(6, result['artifact_count'])
        for chart_id in [
            'component_bug',
            'rolling_valid_bug',
            'open_bug_trend',
            'total_bug_trend',
            'open_bug_aging',
            'daily_new_standard_bug_count',
        ]:
            artifact = cache_service.latest_aggregate_artifact('hsdes', 'nvu-ttl-hsdes', chart_id, 1, '26WW32', '26WW32')
            self.assertIsNotNone(artifact)
            self.assertEqual(ProviderFreshnessStatus.LIVE_SYNCED, artifact.run_metadata_json['freshness_status'])

    def _component_count(self, artifact, component):
        for row in artifact.grafana_rows_json:
            if row.get('dimensions', {}).get('component') == component:
                return row.get('component_bug_count')
        return None

    def _http_error_category_for_status(self, status_code):
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(request.full_url, status_code, 'error', {}, None)

        client = HsdesHttpClient(
            base_url='https://hsdes-api.intel.com/rest',
            auth_mode='kerberos',
            transport='urllib',
            opener=fake_urlopen,
        )
        with self.assertRaises(HsdesProviderError) as context:
            client.execute_saved_query('15017652869', 'tenant', 'subject', ['id'], 0, 100)
        return context.exception.category


class FakeHttpResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self._payload).encode('utf-8')


class FakeProcess:
    def __init__(self, stdout, stderr, returncode):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class JsonOutput:
    def __init__(self):
        self.value = ''

    def write(self, value):
        self.value += value
