import hashlib
import json
import base64
import os
import subprocess
from urllib import error, parse, request

from bug_metrics.app.api.hsdes_projection import HsdesProviderProjectionService
from bug_metrics.app.api.provider_aggregate_contracts import (
    FIRST_HSDES_PROFILE_ID,
)
from bug_metrics.app.api.provider_aggregates import ProviderChartAggregateService
from bug_metrics.app.api.provider_aggregate_contracts import ProviderChartAggregateQuery
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfile, ProjectProviderProfileRegistry

from .cache import ProviderSyncCacheService
from .cache_contracts import ProviderFreshnessStatus


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
        profile_registry: ProjectProviderProfileRegistry | None = None,
    ):
        self._adapter = adapter
        self._cache_service = cache_service or ProviderSyncCacheService()
        self._projection_service = projection_service or HsdesProviderProjectionService()
        self._aggregate_service = aggregate_service or ProviderChartAggregateService(provider_sync_cache_service=self._cache_service)
        self._profile_registry = profile_registry or ProjectProviderProfileRegistry.load_default()

    def sync_nvu_ttl_profile(self, begin_ww: str, end_ww: str, force_refresh: bool = False) -> dict:
        return self.sync_profile(FIRST_HSDES_PROFILE_ID, begin_ww, end_ww, force_refresh)

    def sync_profile(self, profile_id: str, begin_ww: str, end_ww: str, force_refresh: bool = False) -> dict:
        profile_resolution = self._profile_registry.resolve_profile(profile_id)
        if profile_resolution.profile is None:
            return {
                'status': profile_resolution.status,
                'profile_id': profile_id,
                'provider_id': profile_resolution.provider_id,
                'blockers': profile_resolution.blockers,
            }
        profile = profile_resolution.profile
        if profile.provider_id != 'hsdes':
            return {
                'status': 'unsupported',
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'blockers': [{
                    'code': 'provider_sync_adapter_not_available',
                    'message': f'Provider {profile.provider_id} does not have a provider_sync adapter in this command.',
                }],
            }
        source_population = profile.source_population
        query_id = source_population.get('source_query_ref', '')
        refresh = self._cache_service.try_start_refresh(profile.provider_id, profile.profile_id, query_id, force_refresh)
        if not refresh.acquired:
            return {
                'status': refresh.status,
                'profile_id': profile.profile_id,
                'reason': refresh.reason,
            }
        try:
            field_names = self._field_names(profile)
            payload = self._adapter.fetch_saved_query(
                query_id=query_id,
                tenant=source_population.get('tenant_or_site', ''),
                subject=source_population.get('subject_or_issue_type', ''),
                field_names=field_names,
            )
            projection = self._projection_service.normalize_search_page(profile.profile_id, payload)
            source_query = self._source_query(payload, profile, field_names)
            snapshot = self._cache_service.materialize_snapshot(
                provider_id=profile.provider_id,
                profile_id=profile.profile_id,
                source_query=source_query,
                field_set_hash=self._field_set_hash(field_names),
                mapping_version_hash=profile.mapping_version_hash,
                facts=projection['facts'],
                raw_payload={'total': payload.get('total', 0), 'errors': payload.get('errors', [])},
                freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
            )
            artifacts = self._materialize_aggregate_artifacts(snapshot, projection['facts'], begin_ww, end_ww, profile)
            return {
                'status': 'success',
                'profile_id': profile.profile_id,
                'fact_snapshot_id': str(snapshot.id),
                'fact_count': snapshot.record_count,
                'artifact_count': len(artifacts),
                'force_refresh': force_refresh,
            }
        except HsdesProviderError as error:
            self._cache_service.record_failure(profile.provider_id, profile.profile_id, error.category, str(error))
            return {
                'status': 'failed',
                'profile_id': profile.profile_id,
                'error_category': error.category,
            }

    def _materialize_aggregate_artifacts(self, snapshot, facts, begin_ww, end_ww, profile: ProjectProviderProfile):
        artifacts = []
        supported_chart_ids = [
            chart_id
            for chart_id, binding in profile.chart_bindings.items()
            if str(binding.get('support_status', '')).startswith('supported')
        ]
        for chart_id in sorted(supported_chart_ids):
            result = self._aggregate_service.build_hsdes_quality_aggregate_artifact(
                ProviderChartAggregateQuery(profile.provider_id, profile.profile_id, begin_ww, end_ww, chart_id),
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

    def _source_query(self, payload, profile: ProjectProviderProfile, field_names):
        source = dict(profile.source_population)
        source.update({
            'source_query_hash': self._source_query_hash(payload, profile, field_names),
            'mapping_version': str(profile.mapping_version),
            'mapping_version_hash': profile.mapping_version_hash,
        })
        return source

    def _source_query_hash(self, payload, profile: ProjectProviderProfile, field_names):
        encoded = json.dumps({
            'query_id': profile.source_population.get('source_query_ref', ''),
            'total': payload.get('total', 0),
            'field_names': field_names,
        }, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def _field_set_hash(self, field_names):
        encoded = json.dumps(sorted(field_names), separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def _field_names(self, profile: ProjectProviderProfile):
        field_names = []
        for binding in profile.field_bindings.values():
            native_field = binding.get('native_field', '')
            if native_field and native_field not in field_names:
                field_names.append(native_field)
        return field_names
