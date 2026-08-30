import hashlib
import json
import base64
import os
import subprocess
from urllib import error, parse, request

from bug_metrics.app.api.hsdes_projection import HsdesProviderProjectionService
from bug_metrics.app.api.provider_aggregate_contracts import (
    FIRST_HSDES_PROFILE_ID,
    FIRST_HSDES_QUERY_ID,
    FIRST_HSDES_SUBJECT,
    FIRST_HSDES_TENANT,
    MAPPING_VERSION,
    SUPPORTED_HSDES_SEED_CHARTS,
)
from bug_metrics.app.api.provider_aggregates import ProviderChartAggregateService
from bug_metrics.app.api.provider_aggregate_contracts import ProviderChartAggregateQuery

from .cache import ProviderFreshnessStatus, ProviderSyncCacheService


class HsdesProviderError(Exception):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


class HsdesHttpClient:
    def __init__(self, base_url: str, auth_mode: str = 'kerberos', username: str = '',
                 password: str = '', token: str = '', timeout_seconds: int = 30, opener=None,
                 transport: str = 'auto', powershell_runner=None):
        self._base_url = base_url.rstrip('/')
        self._auth_mode = auth_mode
        self._username = username
        self._password = password
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._opener = opener or request.urlopen
        self._transport = transport
        self._powershell_runner = powershell_runner or subprocess.run

    def execute_saved_query(self, query_id, tenant, subject, field_names, start_at, max_results):
        query = parse.urlencode({
            'start_at': start_at,
            'max_results': max_results,
            'tenant': tenant,
            'subject': subject,
            'fields': ','.join(field_names),
        })
        url = f'{self._base_url}{self._saved_query_path(query_id)}?{query}'
        if self._should_use_powershell_transport():
            return self._execute_with_powershell(url)
        http_request = request.Request(url)
        self._apply_auth(http_request)
        try:
            with self._opener(http_request, timeout=self._timeout_seconds) as response:
                payload = self._decode_payload(response.read())
        except error.HTTPError as exception:
            raise HsdesProviderError(self._http_error_category(exception.code), f'HSD-ES HTTP {exception.code}') from exception
        except error.URLError as exception:
            raise HsdesProviderError('network_error', str(exception.reason)) from exception
        except json.JSONDecodeError as exception:
            raise HsdesProviderError('malformed_payload', 'HSD-ES response was not valid JSON.') from exception
        return self._validate_payload(payload)

    def _saved_query_path(self, query_id: str) -> str:
        if self._auth_mode in {'token', 'basic'}:
            return f'/auth/query/execution/{parse.quote(str(query_id))}'
        return f'/query/execution/{parse.quote(str(query_id))}'

    def _apply_auth(self, http_request):
        if self._auth_mode == 'token' and self._token:
            http_request.add_header('Authorization', f'Bearer {self._token}')
        if self._auth_mode == 'basic' and self._username and self._password:
            encoded = base64.b64encode(f'{self._username}:{self._password}'.encode('utf-8')).decode('ascii')
            http_request.add_header('Authorization', f'Basic {encoded}')

    def _http_error_category(self, status_code: int) -> str:
        if status_code == 401:
            return 'auth_failed'
        if status_code == 403:
            return 'permission_denied'
        if status_code == 429:
            return 'rate_limited'
        if status_code >= 500:
            return 'provider_error'
        return 'http_error'

    def _should_use_powershell_transport(self) -> bool:
        if self._transport == 'powershell':
            return True
        return self._transport == 'auto' and self._auth_mode in {'kerberos', 'windows_integrated'} and os.name == 'nt'

    def _execute_with_powershell(self, url: str) -> dict:
        escaped_url = url.replace("'", "''")
        script = (
            '$ProgressPreference = "SilentlyContinue"; '
            f"$response = Invoke-WebRequest -Uri '{escaped_url}' "
            f'-UseDefaultCredentials -UseBasicParsing -TimeoutSec {self._timeout_seconds} '
            '-Headers @{Accept="application/json"}; '
            '$response.Content'
        )
        encoded_script = base64.b64encode(script.encode('utf-16le')).decode('ascii')
        try:
            completed = self._powershell_runner(
                ['powershell', '-NoProfile', '-EncodedCommand', encoded_script],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds + 5,
                env=dict(os.environ),
            )
        except (OSError, subprocess.TimeoutExpired) as exception:
            raise HsdesProviderError('network_error', str(exception)) from exception
        if completed.returncode != 0:
            raise HsdesProviderError(self._powershell_error_category(completed.stderr), self._redacted_error(completed.stderr))
        if not completed.stdout.strip() and completed.stderr.strip():
            raise HsdesProviderError(self._powershell_error_category(completed.stderr), self._redacted_error(completed.stderr))
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exception:
            raise HsdesProviderError('malformed_payload', 'HSD-ES PowerShell response was not valid JSON.') from exception
        return self._validate_payload(payload)

    def _decode_payload(self, payload: bytes) -> dict:
        return json.loads(payload.decode('utf-8'))

    def _validate_payload(self, payload) -> dict:
        if not isinstance(payload, dict):
            raise HsdesProviderError('malformed_payload', 'HSD-ES response JSON must be an object.')
        return payload

    def _powershell_error_category(self, stderr: str) -> str:
        lowered = stderr.lower()
        if '401' in lowered or 'unauthorized' in lowered:
            return 'auth_failed'
        if '403' in lowered or 'forbidden' in lowered:
            return 'permission_denied'
        if '429' in lowered:
            return 'rate_limited'
        if 'timed out' in lowered or 'timeout' in lowered:
            return 'timeout'
        return 'provider_error'

    def _redacted_error(self, message: str) -> str:
        redacted = message
        for token in [self._token, self._password]:
            if token:
                redacted = redacted.replace(token, '[redacted]')
        return redacted


class HsdesSavedQueryAdapter:
    def __init__(self, client, page_size: int = 100):
        self._client = client
        self._page_size = page_size

    def fetch_saved_query(self, query_id: str, tenant: str, subject: str, field_names: list[str]) -> dict:
        start_at = 0
        articles = []
        errors = []
        total = 0
        while True:
            page = self._client.execute_saved_query(query_id, tenant, subject, field_names, start_at, self._page_size)
            if not isinstance(page, dict):
                raise HsdesProviderError('malformed_payload', 'HSD-ES saved query page must be a JSON object.')
            page_articles = page.get('articles') or page.get('data') or page.get('results') or []
            if page.get('errors'):
                raise HsdesProviderError('partial_response', 'HSD-ES returned errors with the saved query page.')
            if not isinstance(page_articles, list):
                raise HsdesProviderError('malformed_payload', 'HSD-ES saved query page must contain an article list.')
            articles.extend(page_articles)
            total = int(page.get('total', len(articles)) or len(articles))
            returned_count = len(page_articles)
            if returned_count == 0 and len(articles) < total:
                raise HsdesProviderError('partial_response', 'HSD-ES saved query pagination stopped before total was fetched.')
            if returned_count == 0 or start_at + returned_count >= total:
                break
            start_at += returned_count
        return {
            'profile_id': FIRST_HSDES_PROFILE_ID,
            'seeded_from_query_id': query_id,
            'articles': articles,
            'errors': errors,
            'total': total,
        }


class HsdesSavedQuerySyncService:
    def __init__(
        self,
        adapter: HsdesSavedQueryAdapter,
        cache_service: ProviderSyncCacheService | None = None,
        projection_service: HsdesProviderProjectionService | None = None,
        aggregate_service: ProviderChartAggregateService | None = None,
    ):
        self._adapter = adapter
        self._cache_service = cache_service or ProviderSyncCacheService()
        self._projection_service = projection_service or HsdesProviderProjectionService()
        self._aggregate_service = aggregate_service or ProviderChartAggregateService(provider_sync_cache_service=self._cache_service)

    def sync_nvu_ttl_profile(self, begin_ww: str, end_ww: str, force_refresh: bool = False) -> dict:
        refresh = self._cache_service.try_start_refresh('hsdes', FIRST_HSDES_PROFILE_ID, FIRST_HSDES_QUERY_ID, force_refresh)
        if not refresh.acquired:
            return {
                'status': refresh.status,
                'profile_id': FIRST_HSDES_PROFILE_ID,
                'reason': refresh.reason,
            }
        try:
            payload = self._adapter.fetch_saved_query(
                query_id=FIRST_HSDES_QUERY_ID,
                tenant=FIRST_HSDES_TENANT,
                subject=FIRST_HSDES_SUBJECT,
                field_names=self._field_names(),
            )
            projection = self._projection_service.normalize_search_page(FIRST_HSDES_PROFILE_ID, payload)
            source_query = self._source_query(payload)
            snapshot = self._cache_service.materialize_snapshot(
                provider_id='hsdes',
                profile_id=FIRST_HSDES_PROFILE_ID,
                source_query=source_query,
                field_set_hash=self._field_set_hash(self._field_names()),
                mapping_version_hash=self._mapping_version_hash(),
                facts=projection['facts'],
                raw_payload={'total': payload.get('total', 0), 'errors': payload.get('errors', [])},
                freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
            )
            artifacts = self._materialize_aggregate_artifacts(snapshot, projection['facts'], begin_ww, end_ww)
            return {
                'status': 'success',
                'profile_id': FIRST_HSDES_PROFILE_ID,
                'fact_snapshot_id': str(snapshot.id),
                'fact_count': snapshot.record_count,
                'artifact_count': len(artifacts),
                'force_refresh': force_refresh,
            }
        except HsdesProviderError as error:
            self._cache_service.record_failure('hsdes', FIRST_HSDES_PROFILE_ID, error.category, str(error))
            return {
                'status': 'failed',
                'profile_id': FIRST_HSDES_PROFILE_ID,
                'error_category': error.category,
            }

    def _materialize_aggregate_artifacts(self, snapshot, facts, begin_ww, end_ww):
        artifacts = []
        for chart_id in sorted(SUPPORTED_HSDES_SEED_CHARTS):
            result = self._aggregate_service.build_hsdes_quality_aggregate_artifact(
                ProviderChartAggregateQuery('hsdes', FIRST_HSDES_PROFILE_ID, begin_ww, end_ww, chart_id),
                facts,
                ProviderFreshnessStatus.LIVE_SYNCED,
            )
            artifacts.append(self._cache_service.store_aggregate_artifact(
                snapshot=snapshot,
                chart_id=chart_id,
                chart_version=1,
                begin_ww=begin_ww,
                end_ww=end_ww,
                rows=[row.to_dict() for row in result.rows],
                grafana_rows=result.grafana_rows,
                source_population=result.source_population,
                run_metadata=result.run_metadata,
                status=result.status,
                reason=result.reason,
            ))
        return artifacts

    def _source_query(self, payload):
        source = {
            'ownership_type': 'provider_owned_saved_query',
            'source_query_ref': FIRST_HSDES_QUERY_ID,
            'source_query_hash': self._source_query_hash(payload),
            'source_query_name': 'NVU All Bugs',
            'tenant_or_site': FIRST_HSDES_TENANT,
            'subject_or_issue_type': FIRST_HSDES_SUBJECT,
            'mapping_version': str(MAPPING_VERSION),
        }
        return source

    def _source_query_hash(self, payload):
        encoded = json.dumps({
            'query_id': FIRST_HSDES_QUERY_ID,
            'total': payload.get('total', 0),
            'field_names': self._field_names(),
        }, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def _field_set_hash(self, field_names):
        encoded = json.dumps(sorted(field_names), separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def _mapping_version_hash(self):
        return hashlib.sha256(f'hsdes:{FIRST_HSDES_PROFILE_ID}:{MAPPING_VERSION}'.encode('utf-8')).hexdigest()

    def _field_names(self):
        return [
            'id',
            'rev',
            'HSD_type',
            'status',
            'reason',
            'priority',
            'exposure',
            'component',
            'release',
            'release_affected',
            'target_MS',
            'owner',
            'submitted_by',
            'submitted_date',
            'updated_date',
            'implemented_date',
            'closed_date',
            'team_found',
            'pss_escape',
            'days_open',
        ]
