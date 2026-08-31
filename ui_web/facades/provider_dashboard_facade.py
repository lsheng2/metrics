from urllib.parse import urlencode

from bug_metrics.app.api import ProviderChartAggregateQuery, ProviderChartEvidenceQuery
from bug_metrics.app.api.provider_aggregate_contracts import PROVIDER_CHART_CONTRACT_VERSION
from bug_metrics.app.api.provider_aggregates import iso_date_value, ww_range_to_dates
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import JiraScopeConfig


FIRST_HSDES_ACCESS_CHECK_URL = 'https://hsdes.intel.com/appstore/generalapps/#/pages/community/1607367026?queryId=15017652869'


class ProviderDashboardFacade:
    def __init__(self, bug_trend_api):
        self._bug_trend_api = bug_trend_api
        self._profile_registry = ProjectProviderProfileRegistry.load_default()

    def get_provider_chart_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                   chart_id: str, chart_version: int = 1, fact_snapshot_id: str = '',
                                   range_mode: str = 'ww', begin_date: str = '', end_date: str = '') -> dict:
        resolved_provider_id = self._resolve_provider_id(provider_id, profile_id)
        result = self._bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery(
                provider_id=resolved_provider_id,
                profile_id=profile_id,
                begin_ww=begin_ww,
                end_ww=end_ww,
                chart_id=chart_id,
                chart_version=chart_version,
                fact_snapshot_id=fact_snapshot_id,
                range_mode=range_mode,
                begin_date=begin_date,
                end_date=end_date,
            )
        )
        return result.to_dict()

    def get_provider_chart_evidence_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                            chart_id: str, calculation_run_id: str, bucket_id: str = '',
                                            series_name: str = '', chart_version: int = 1, fact_snapshot_id: str = '',
                                            owner: str = '', status: str = '', severity: str = '',
                                            component: str = '', text: str = '', range_mode: str = 'ww',
                                            begin_date: str = '', end_date: str = '') -> dict:
        resolved_provider_id = self._resolve_provider_id(provider_id, profile_id)
        return self._bug_trend_api.get_provider_chart_evidence(
            ProviderChartEvidenceQuery(
                provider_id=resolved_provider_id,
                profile_id=profile_id,
                begin_ww=begin_ww,
                end_ww=end_ww,
                chart_id=chart_id,
                chart_version=chart_version,
                calculation_run_id=calculation_run_id,
                selected_bucket_id=bucket_id,
                selected_series_name=series_name,
                fact_snapshot_id=fact_snapshot_id,
                owner=owner,
                status=status,
                severity=severity,
                component=component,
                text=text,
                range_mode=range_mode,
                begin_date=begin_date,
                end_date=end_date,
            )
        )

    def get_provider_profile_readiness_payload(self, provider_id: str, profile_id: str, range_mode: str = 'ww',
                                               begin_ww: str = '', end_ww: str = '', begin_date: str = '',
                                               end_date: str = '') -> dict:
        resolved_provider_id = self._resolve_provider_id(provider_id, profile_id)
        readiness = self._bug_trend_api.get_provider_profile_readiness(resolved_provider_id, profile_id)
        readiness['contract_version'] = PROVIDER_CHART_CONTRACT_VERSION
        readiness['provider_id'] = resolved_provider_id
        readiness['profile_status_rows'] = [self._profile_status_row(
            readiness,
            self._time_range_action_url(profile_id, range_mode, begin_ww, end_ww, begin_date, end_date),
        )]
        return readiness

    def get_provider_profile_time_range_action_url(self, provider_id: str, profile_id: str, range_mode: str = 'ww',
                                                   begin_ww: str = '', end_ww: str = '', begin_date: str = '',
                                                   end_date: str = '') -> str:
        self._resolve_provider_id(provider_id, profile_id)
        return self._time_range_action_url(profile_id, range_mode, begin_ww, end_ww, begin_date, end_date)

    def _resolve_provider_id(self, provider_id: str, profile_id: str) -> str:
        explicit_provider_id = provider_id or ''
        profile_provider_id = self._provider_id_for_profile(profile_id)
        if explicit_provider_id and profile_provider_id and explicit_provider_id != profile_provider_id:
            raise ValueError(f'Provider {explicit_provider_id} does not match selected profile {profile_id}.')
        if explicit_provider_id:
            return explicit_provider_id
        if profile_provider_id:
            return profile_provider_id
        raise ValueError(f'Provider could not be resolved for profile {profile_id}.')

    def _provider_id_for_profile(self, profile_id: str) -> str:
        resolution = self._profile_registry.resolve_profile(profile_id)
        if resolution.profile is not None:
            return resolution.profile.provider_id
        if JiraScopeConfig.objects.filter(enabled=True, name=profile_id).exists():
            return 'jira'
        return ''

    def _profile_status_row(self, readiness: dict, time_range_action_url: str = '') -> dict:
        scope_labels = readiness.get('scope_labels', {})
        source_query = readiness.get('source_query', {})
        blockers = readiness.get('blockers', [])
        sync_cache = readiness.get('sync_cache', {})
        return {
            'provider_id': readiness.get('provider_id', ''),
            'profile_id': readiness.get('profile_id', ''),
            'status': readiness.get('status', ''),
            'data_status': self._profile_data_status(readiness),
            'data_status_reason': self._profile_data_status_reason(readiness),
            'ip': self._scope_label_value(scope_labels, 'ip'),
            'project_or_product': self._scope_label_value(scope_labels, 'project_or_product'),
            'milestone': self._scope_label_value(scope_labels, 'milestone'),
            'scope_label_source': self._scope_label_source(scope_labels),
            'source_query_ownership': source_query.get('ownership_type', ''),
            'source_query_ref': source_query.get('source_query_ref', ''),
            'source_query_name': source_query.get('source_query_name', ''),
            'mapping_version': readiness.get('mapping_version', ''),
            'override_state': 'profile_default',
            'save_profile_action': 'available_in_profile_editor',
            'auth_action_label': self._profile_auth_action_label(readiness),
            'auth_action_url': self._profile_auth_action_url(readiness),
            'time_range_action_label': 'Sync Time Range' if time_range_action_url else '',
            'time_range_action_url': time_range_action_url,
            'blocker_count': len(blockers),
            'freshness_status': sync_cache.get('freshness_status', ''),
            'latest_snapshot_id': sync_cache.get('latest_snapshot_id', ''),
            'latest_successful_sync_at': sync_cache.get('latest_successful_sync_at', ''),
            'cache_age_seconds': sync_cache.get('cache_age_seconds', ''),
            'error_category': sync_cache.get('error_category', ''),
        }

    def _profile_data_status(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') in {'seeded_preview', 'live_synced', 'failed', 'stale'}:
            return readiness.get('status')
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'blocked':
            return 'configuration_required'
        return readiness.get('status', '')

    def _profile_data_status_reason(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'seeded_preview':
            return 'HSD-ES seed facts can render supported preview charts; live HSD-ES sync still requires backend credential, saved-query permission, lookup and field-binding validation.'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'live_synced':
            return 'HSD-ES live sync has materialized provider facts and dashboard aggregate artifacts for this profile.'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'failed':
            return 'HSD-ES live sync failed; the dashboard keeps the latest successful local artifact when one exists.'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'stale':
            return 'HSD-ES live sync artifacts are available but older than the configured freshness window.'
        if readiness.get('provider_id') == 'hsdes':
            return 'HSD-ES quality facts require confirmed field bindings and runtime permission validation before aggregate generation.'
        blockers = readiness.get('blockers', [])
        return blockers[0].get('message', '') if blockers else ''

    def _profile_auth_action_label(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes':
            return 'Open HSD-ES saved query / sign in'
        return ''

    def _profile_auth_action_url(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes':
            return FIRST_HSDES_ACCESS_CHECK_URL
        return ''

    def _time_range_action_url(self, profile_id: str, range_mode: str, begin_ww: str, end_ww: str,
                               begin_date: str, end_date: str) -> str:
        normalized_range_mode = (range_mode or 'ww').strip().lower()
        try:
            if normalized_range_mode == 'date':
                begin = iso_date_value(begin_date, 'begin_date')
                end = iso_date_value(end_date, 'end_date')
            else:
                begin, end = ww_range_to_dates(begin_ww, end_ww)
        except ValueError:
            return ''
        if begin > end:
            return ''
        query = urlencode({
            'orgId': '1',
            'var-profile_id': profile_id,
            'var-range_mode': normalized_range_mode,
            'var-begin_ww': begin_ww,
            'var-end_ww': end_ww,
            'from': f'{begin.isoformat()}T00:00:00',
            'to': f'{end.isoformat()}T23:59:59',
            'timezone': 'browser',
        })
        return f'/d/ip-quality-dashboard/ip-quality-dashboard?{query}'

    def _scope_label_value(self, scope_labels: dict, name: str) -> str:
        return str(scope_labels.get(name, {}).get('value', ''))

    def _scope_label_source(self, scope_labels: dict) -> str:
        sources = {
            str(label.get('source', ''))
            for label in scope_labels.values()
            if isinstance(label, dict) and label.get('source')
        }
        return ','.join(sorted(sources))
