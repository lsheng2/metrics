from .provider_aggregate_contracts import (
    PROVIDER_CHART_EVIDENCE_CAPABILITIES,
    SUPPORTED_HSDES_SEED_CHARTS,
    static_scope_labels_for_profile,
)
from .hsdes_readiness_contract import FIRST_HSDES_EXPECTED_FIELD_SET, hsdes_api_contract
from .provider_profile_registry import ChartRecipeRequirement, ProjectProviderProfile, ProjectProviderProfileRegistry
from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


class ProviderProfileReadinessService:
    def __init__(self, provider_sync_cache_service=None, profile_registry=None):
        self._provider_sync_cache_service = provider_sync_cache_service or ProviderSyncCacheService()
        self._profile_registry = profile_registry or ProjectProviderProfileRegistry.load_default()

    def get_readiness(self, provider_id: str, profile_id: str) -> dict:
        resolution = self._resolve_profile(provider_id, profile_id)
        if resolution.profile is None:
            return self._profile_resolution_readiness(resolution)
        profile = resolution.profile
        if profile.provider_id == 'hsdes':
            return self._first_hsdes_readiness(profile)
        if profile.provider_id == 'jira':
            return self._jira_readiness(profile)
        return self._unsupported_readiness(profile.provider_id, profile.profile_id)

    def _first_hsdes_readiness(self, profile: ProjectProviderProfile) -> dict:
        sync_cache = self._provider_sync_cache_service.profile_cache_status(profile.provider_id, profile.profile_id)
        status = sync_cache['status']
        if status == ProviderFreshnessStatus.SEEDED_PREVIEW:
            blockers = self._hsdes_blockers()
        elif status == ProviderFreshnessStatus.LIVE_SYNCED:
            blockers = []
        else:
            blockers = self._hsdes_blockers()
        return self._readiness_payload(profile, status, blockers, hsdes_api_contract(), sync_cache)

    def validate_drift(self, provider_id: str, profile_id: str, observed_profile: dict) -> dict:
        resolution = self._resolve_profile(provider_id, profile_id)
        if resolution.profile is None:
            return self._unsupported_drift_result(provider_id, profile_id)
        profile = resolution.profile
        if profile.provider_id != 'hsdes':
            return self._unsupported_drift_result(profile.provider_id, profile.profile_id)
        drift_items = self._hsdes_drift_items(profile, observed_profile)
        status = 'drifted' if drift_items else 'current'
        return {
            'provider_id': profile.provider_id,
            'profile_id': profile.profile_id,
            'status': status,
            'aggregate_generation_allowed': False,
            'reason': self._drift_reason(status),
            'drift_items': drift_items,
        }

    def get_capability_manifest(self, provider_id: str, profile_id: str) -> dict:
        resolution = self._resolve_profile(provider_id, profile_id)
        if resolution.profile is None:
            return {
                'provider_id': resolution.provider_id,
                'profile_id': resolution.profile_id,
                'manifest_version': '0.1',
                'capabilities': [
                    self._capability('provider_profile', resolution.status, resolution.blockers[0]['message']),
                ],
            }
        profile = resolution.profile
        if profile.provider_id == 'hsdes':
            return self._first_hsdes_capability_manifest(profile)
        if profile.provider_id == 'jira':
            return self._jira_capability_manifest(profile)
        return {
            'provider_id': profile.provider_id,
            'profile_id': profile.profile_id,
            'manifest_version': '0.1',
            'capabilities': [
                self._capability('provider_profile', 'unsupported', f'Provider {profile.provider_id} does not have a capability manifest.'),
            ],
        }

    def _resolve_profile(self, provider_id: str, profile_id: str):
        resolution = self._profile_registry.resolve_profile(profile_id)
        if resolution.profile is None:
            return resolution
        profile = resolution.profile
        if provider_id and provider_id != profile.provider_id:
            return type(resolution)(
                status='unsupported',
                profile_id=profile.profile_id,
                provider_id=provider_id,
                profile=None,
                blockers=[{
                    'code': 'profile_provider_mismatch',
                    'message': f'Provider {provider_id} does not match selected profile {profile_id}.',
                }],
            )
        return resolution

    def _profile_resolution_readiness(self, resolution) -> dict:
        return {
            'provider_id': resolution.provider_id,
            'profile_id': resolution.profile_id,
            'status': resolution.status,
            'freshness_status': resolution.status,
            'mapping_version': '',
            'mapping_version_hash': '',
            'source_query': {},
            'source_population': {},
            'scope_labels': {},
            'sync_cache': {},
            'freshness': {'status': resolution.status, 'source': 'profile_resolution'},
            'api_contract': {},
            'chart_bindings': [],
            'chart_support': [],
            'blockers': resolution.blockers,
        }

    def _jira_readiness(self, profile: ProjectProviderProfile) -> dict:
        return self._readiness_payload(profile, profile.readiness_policy.get('ready_status', 'ready'), [], {}, {})

    def _unsupported_readiness(self, provider_id: str, profile_id: str) -> dict:
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'status': 'unsupported',
            'freshness_status': 'unsupported',
            'mapping_version': '',
            'mapping_version_hash': '',
            'source_query': {},
            'source_population': {},
            'scope_labels': {},
            'sync_cache': {},
            'freshness': {'status': 'unsupported', 'source': 'provider_profile'},
            'api_contract': {},
            'chart_bindings': [],
            'chart_support': [],
            'blockers': [
                {
                    'code': 'provider_not_supported',
                    'message': f'Provider {provider_id} does not have a profile readiness contract.',
                }
            ],
        }

    def list_profile_health(self) -> list[dict]:
        return [self._profile_health_row(profile) for profile in self._profile_registry.list_profiles()]

    def _readiness_payload(self, profile: ProjectProviderProfile, status: str, blockers: list[dict],
                           api_contract: dict, sync_cache: dict) -> dict:
        source_population = self._source_query(profile)
        freshness_status = sync_cache.get('freshness_status') or status
        return {
            'provider_id': profile.provider_id,
            'profile_id': profile.profile_id,
            'status': status,
            'freshness_status': freshness_status,
            'mapping_version': profile.mapping_version,
            'mapping_version_hash': profile.mapping_version_hash,
            'source_query': source_population,
            'source_population': source_population,
            'scope_labels': static_scope_labels_for_profile(profile.profile_id),
            'sync_cache': sync_cache,
            'freshness': {
                'status': freshness_status,
                'source': 'provider_sync_cache' if sync_cache else 'profile_readiness_policy',
                'latest_snapshot_id': sync_cache.get('latest_snapshot_id', ''),
                'latest_successful_sync_at': sync_cache.get('latest_successful_sync_at', ''),
                'cache_age_seconds': sync_cache.get('cache_age_seconds', ''),
            },
            'api_contract': api_contract,
            'chart_bindings': self._profile_chart_bindings(profile),
            'chart_support': self._profile_chart_support(profile),
            'blockers': blockers,
        }

    def _profile_health_row(self, profile: ProjectProviderProfile) -> dict:
        readiness = self.get_readiness(profile.provider_id, profile.profile_id)
        source_population = readiness.get('source_population', {})
        freshness = readiness.get('freshness', {})
        supported_charts = [
            item['chart_id']
            for item in readiness.get('chart_support', [])
            if item.get('support_status') == 'supported'
        ]
        deferred_charts = [
            item['chart_id']
            for item in readiness.get('chart_support', [])
            if item.get('support_status') == 'deferred'
        ]
        sync_cache = readiness.get('sync_cache', {})
        return {
            'provider_id': readiness.get('provider_id', ''),
            'profile_id': readiness.get('profile_id', ''),
            'status': readiness.get('status', ''),
            'freshness_status': freshness.get('status', readiness.get('freshness_status', '')),
            'latest_snapshot_id': sync_cache.get('latest_snapshot_id', ''),
            'latest_successful_sync_at': sync_cache.get('latest_successful_sync_at', ''),
            'cache_age_seconds': sync_cache.get('cache_age_seconds', ''),
            'source_query_ownership': source_population.get('ownership_type', ''),
            'source_query_ref': source_population.get('source_query_ref', ''),
            'source_query_name': source_population.get('source_query_name', ''),
            'mapping_version': readiness.get('mapping_version', ''),
            'mapping_version_hash': readiness.get('mapping_version_hash', ''),
            'supported_chart_ids': ', '.join(supported_charts),
            'deferred_chart_ids': ', '.join(deferred_charts),
            'error_category': sync_cache.get('error_category', ''),
            'last_error': sync_cache.get('last_error', ''),
        }

    def _first_hsdes_capability_manifest(self, profile: ProjectProviderProfile) -> dict:
        return {
            'provider_id': profile.provider_id,
            'profile_id': profile.profile_id,
            'manifest_version': '0.1',
            'capabilities': [
                self._capability('article_search', 'configuration_required', 'HSD-ES EQL search requires runtime validation of saved-query permissions, pagination and field set before sync.'),
                self._capability('article_detail', 'configuration_required', 'HSD-ES article detail requires runtime validation of detail, links, children and comments permissions.'),
                self._capability('lookup_metadata', 'configuration_required', 'HSD-ES lookup group ids for target NVU fields require runtime validation.'),
                self._capability('quality_facts', 'seeded_preview', 'HSD-ES seed facts support preview quality aggregates; live HSD-ES sync still requires backend access, lookup and field-binding validation.'),
                self._capability('correlation_facts', 'configuration_required', 'HSD-ES correlation facts require confirmed external id, link, title, owner, release and time-window mappings.'),
                self._capability('planning_actions', 'unsupported', 'Jira-owned planning concepts such as boards, sprints and issue transitions are not HSD-ES-native capabilities.'),
                self._capability('write_actions', 'unsupported', 'HSD-ES writes remain disabled until tenant/subject required fields, permission model, send_mail behavior and approval policy are reviewed.'),
            ],
        }

    def _jira_capability_manifest(self, profile: ProjectProviderProfile) -> dict:
        return {
            'provider_id': profile.provider_id,
            'profile_id': profile.profile_id,
            'manifest_version': '0.1',
            'capabilities': [
                self._capability('issue_search', 'supported', 'Jira search is supported through Metrics-managed JQL or future provider-owned saved filters.'),
                self._capability('quality_facts', 'supported', 'Jira quality facts support first-wave parity charts.'),
                self._capability('write_actions', 'preview_only', 'Jira writes are action-plan gated and require approval before execution.'),
            ],
        }

    def _capability(self, capability_id: str, status: str, reason: str) -> dict:
        return {
            'capability_id': capability_id,
            'status': status,
            'reason': reason,
        }

    def _source_query(self, profile: ProjectProviderProfile) -> dict:
        source_population = dict(profile.source_population)
        source_population['profile_id'] = profile.profile_id
        source_population['provider_id'] = profile.provider_id
        source_population['mapping_version'] = str(profile.mapping_version)
        source_population['mapping_version_hash'] = profile.mapping_version_hash
        return source_population

    def _profile_chart_bindings(self, profile: ProjectProviderProfile) -> list[dict]:
        return [
            self._chart_binding(
                chart_id,
                binding.get('support_status', 'configuration_required'),
                list(binding.get('candidate_native_fields', [])),
                list(binding.get('blocker_codes', [])),
                list(binding.get('required_canonical_fields', [])),
            )
            for chart_id, binding in sorted(profile.chart_bindings.items())
        ]

    def _profile_chart_support(self, profile: ProjectProviderProfile) -> list[dict]:
        return [
            self._resolve_chart_support(profile, chart_id, binding).to_binding()
            for chart_id, binding in sorted(profile.chart_bindings.items())
        ]

    def _resolve_chart_support(self, profile: ProjectProviderProfile, chart_id: str, binding: dict):
        return self._profile_registry.resolve_chart_support(
            profile.profile_id,
            ChartRecipeRequirement(
                chart_id=chart_id,
                chart_version=1,
                required_canonical_fields=list(binding.get('required_canonical_fields', [])),
                provider_capability='quality_facts',
                evidence_capability=PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only'),
            ),
            self._provider_capabilities(profile.provider_id),
        )

    def _provider_capabilities(self, provider_id: str) -> dict[str, str]:
        if provider_id == 'jira':
            return {'quality_facts': 'supported'}
        if provider_id == 'hsdes':
            return {'quality_facts': 'seeded_preview'}
        return {}

    def _chart_binding(self, chart_id: str, support_status: str, candidate_native_fields: list[str],
                       blocker_codes: list[str], required_canonical_fields: list[str] | None = None) -> dict:
        return {
            'chart_id': chart_id,
            'support_status': support_status,
            'evidence_capability': PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only'),
            'required_canonical_fields': required_canonical_fields or [],
            'candidate_native_fields': candidate_native_fields,
            'blocker_codes': blocker_codes,
        }

    def _hsdes_blockers(self) -> list[dict]:
        return [
            {
                'code': 'hsdes_service_account_permission_not_runtime_verified',
                'message': 'Saved query, article detail, lookup, comment, child and link permissions require runtime validation with the target service account.',
            },
            {
                'code': 'hsdes_lookup_group_ids_not_runtime_verified',
                'message': 'Lookup group ids for NVU family, release, component, status, owner and severity options require runtime validation.',
            },
            {
                'code': 'hsdes_chart_field_bindings_not_runtime_verified',
                'message': f'Only seed-backed charts are available now: {", ".join(sorted(SUPPORTED_HSDES_SEED_CHARTS))}. Remaining first-wave quality chart bindings require runtime validation before live HSD-ES aggregates can be marked supported.',
            },
        ]

    def _hsdes_drift_items(self, profile: ProjectProviderProfile, observed_profile: dict) -> list[dict]:
        source_population = profile.source_population
        expected_values = {
            'source_query_ref': source_population.get('source_query_ref', ''),
            'tenant_or_site': source_population.get('tenant_or_site', ''),
            'subject_or_issue_type': source_population.get('subject_or_issue_type', ''),
            'criteria_snapshot': source_population.get('criteria_snapshot', ''),
        }
        drift_items = [
            {
                'field': field_name,
                'expected': expected_value,
                'observed': observed_profile.get(field_name, ''),
            }
            for field_name, expected_value in expected_values.items()
            if observed_profile.get(field_name, '') != expected_value
        ]
        observed_field_set = frozenset(observed_profile.get('field_set', []))
        expected_field_set = self._expected_field_set(profile)
        if observed_field_set != expected_field_set:
            drift_items.append({
                'field': 'field_set',
                'expected': sorted(expected_field_set),
                'observed': sorted(observed_field_set),
            })
        return drift_items

    def _expected_field_set(self, profile: ProjectProviderProfile) -> frozenset[str]:
        return frozenset(
            binding.get('native_field', '')
            for binding in profile.field_bindings.values()
            if binding.get('native_field')
        )

    def _drift_reason(self, status: str) -> str:
        if status == 'drifted':
            return 'Observed HSD-ES saved query metadata drifted; review the HSD-ES profile before aggregate generation.'
        return 'Observed HSD-ES saved query metadata matches the configured profile, but aggregate generation still requires chart binding validation.'

    def _unsupported_drift_result(self, provider_id: str, profile_id: str) -> dict:
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'status': 'unsupported',
            'aggregate_generation_allowed': False,
            'reason': f'Provider {provider_id} does not have a profile drift contract.',
            'drift_items': [],
        }
