from .provider_aggregate_contracts import (
    DEFERRED_CHART_REASONS,
    FIRST_HSDES_CRITERIA_SNAPSHOT,
    FIRST_HSDES_PROFILE_ID,
    FIRST_HSDES_QUERY_ID,
    FIRST_HSDES_SOURCE_QUERY_NAME,
    FIRST_HSDES_SUBJECT,
    FIRST_HSDES_TENANT,
    MAPPING_VERSION,
    PROVIDER_CHART_EVIDENCE_CAPABILITIES,
    SUPPORTED_HSDES_SEED_CHARTS,
    SUPPORTED_JIRA_CHARTS,
    static_scope_labels_for_profile,
)
from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


FIRST_HSDES_EXPECTED_FIELD_SET = frozenset({
    'id',
    'rev',
    'fieldValues',
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
})


class ProviderProfileReadinessService:
    def __init__(self, provider_sync_cache_service=None):
        self._provider_sync_cache_service = provider_sync_cache_service or ProviderSyncCacheService()

    def get_readiness(self, provider_id: str, profile_id: str) -> dict:
        if provider_id == 'hsdes' and profile_id == FIRST_HSDES_PROFILE_ID:
            return self._first_hsdes_readiness()
        if provider_id == 'jira':
            return self._jira_readiness(provider_id, profile_id)
        return self._unsupported_readiness(provider_id, profile_id)

    def _first_hsdes_readiness(self) -> dict:
        sync_cache = self._provider_sync_cache_service.profile_cache_status('hsdes', FIRST_HSDES_PROFILE_ID)
        status = sync_cache['status']
        if status == ProviderFreshnessStatus.SEEDED_PREVIEW:
            blockers = self._hsdes_blockers()
        elif status == ProviderFreshnessStatus.LIVE_SYNCED:
            blockers = []
        else:
            blockers = self._hsdes_blockers()
        return {
            'provider_id': 'hsdes',
            'profile_id': FIRST_HSDES_PROFILE_ID,
            'status': status,
            'mapping_version': MAPPING_VERSION,
            'source_query': {
                'ownership_type': 'provider_owned_saved_query',
                'source_query_ref': FIRST_HSDES_QUERY_ID,
                'source_query_name': FIRST_HSDES_SOURCE_QUERY_NAME,
                'tenant_or_site': FIRST_HSDES_TENANT,
                'subject_or_issue_type': FIRST_HSDES_SUBJECT,
            },
            'scope_labels': static_scope_labels_for_profile(FIRST_HSDES_PROFILE_ID),
            'sync_cache': sync_cache,
            'api_contract': self._hsdes_api_contract(),
            'chart_bindings': self._hsdes_chart_bindings(),
            'blockers': blockers,
        }

    def validate_drift(self, provider_id: str, profile_id: str, observed_profile: dict) -> dict:
        if provider_id != 'hsdes' or profile_id != FIRST_HSDES_PROFILE_ID:
            return self._unsupported_drift_result(provider_id, profile_id)
        drift_items = self._hsdes_drift_items(observed_profile)
        status = 'drifted' if drift_items else 'current'
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'status': status,
            'aggregate_generation_allowed': False,
            'reason': self._drift_reason(status),
            'drift_items': drift_items,
        }

    def get_capability_manifest(self, provider_id: str, profile_id: str) -> dict:
        if provider_id == 'hsdes' and profile_id == FIRST_HSDES_PROFILE_ID:
            return self._first_hsdes_capability_manifest()
        if provider_id == 'jira':
            return self._jira_capability_manifest(provider_id, profile_id)
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'manifest_version': '0.1',
            'capabilities': [
                self._capability('provider_profile', 'unsupported', f'Provider {provider_id} does not have a capability manifest.'),
            ],
        }

    def _jira_readiness(self, provider_id: str, profile_id: str) -> dict:
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'status': 'ready',
            'mapping_version': MAPPING_VERSION,
            'source_query': {
                'ownership_type': 'metrics_managed_native_query',
            },
            'scope_labels': static_scope_labels_for_profile(profile_id),
            'api_contract': {},
            'chart_bindings': [
                {
                    'chart_id': chart_id,
                    'support_status': 'supported',
                    'evidence_capability': PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only'),
                    'candidate_native_fields': [],
                    'blocker_codes': [],
                }
                for chart_id in sorted(SUPPORTED_JIRA_CHARTS)
            ],
            'blockers': [],
        }

    def _unsupported_readiness(self, provider_id: str, profile_id: str) -> dict:
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'status': 'unsupported',
            'mapping_version': '',
            'source_query': {},
            'scope_labels': {},
            'api_contract': {},
            'chart_bindings': [],
            'blockers': [
                {
                    'code': 'provider_not_supported',
                    'message': f'Provider {provider_id} does not have a profile readiness contract.',
                }
            ],
        }

    def _first_hsdes_capability_manifest(self) -> dict:
        return {
            'provider_id': 'hsdes',
            'profile_id': FIRST_HSDES_PROFILE_ID,
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

    def _jira_capability_manifest(self, provider_id: str, profile_id: str) -> dict:
        return {
            'provider_id': provider_id,
            'profile_id': profile_id,
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

    def _hsdes_api_contract(self) -> dict:
        return {
            'identity_fields': {
                'article_id': 'id',
                'revision': 'rev',
                'tenant': FIRST_HSDES_TENANT,
                'subject': FIRST_HSDES_SUBJECT,
            },
            'detail': {
                'endpoint': '/rest/article/{id}',
                'status': 'docs_confirmed_pending_runtime_validation',
            },
            'search': {
                'endpoint': '/rest/query/execution/eql',
                'query_language': 'EQL',
                'status': 'docs_confirmed_pending_runtime_validation',
            },
            'pagination': {
                'offset_parameter': 'start_at',
                'limit_parameter': 'max_results',
                'status': 'docs_confirmed_pending_runtime_validation',
            },
            'payload': {
                'field_values': 'fieldValues',
                'expected_field_set': sorted(FIRST_HSDES_EXPECTED_FIELD_SET),
                'status': 'docs_confirmed_pending_runtime_validation',
            },
            'lookups': {
                'static_lookup_hint': 'schema/lookupvalue?lookup_group=...',
                'status': 'requires_runtime_validation',
            },
            'relations': {
                'links': '/rest/article/{id}/links',
                'children': '/rest/article/{id}/children',
                'comments': 'comments-as-articles',
                'status': 'requires_runtime_validation',
            },
            'permissions': {
                'status': 'requires_runtime_validation',
            },
        }

    def _hsdes_chart_bindings(self) -> list[dict]:
        bindings = [
            self._chart_binding(
                'component_bug',
                'supported_from_seed_facts',
                ['component', 'id', 'HSD_type'],
                ['hsdes_live_sync_not_configured'],
            ),
            self._chart_binding(
                'rolling_valid_bug',
                'supported_from_seed_facts',
                ['submitted_date', 'priority', 'exposure', 'status', 'HSD_type'],
                ['hsdes_live_sync_not_configured'],
            ),
            self._chart_binding(
                'open_bug_trend',
                'supported_from_seed_facts',
                ['submitted_date', 'updated_date', 'implemented_date', 'closed_date', 'status', 'priority', 'exposure'],
                ['hsdes_live_sync_not_configured'],
            ),
            self._chart_binding(
                'total_bug_trend',
                'supported_from_seed_facts',
                ['submitted_date', 'closed_date', 'status', 'HSD_type'],
                ['hsdes_live_sync_not_configured'],
            ),
            self._chart_binding(
                'open_bug_aging',
                'supported_from_seed_facts',
                ['submitted_date', 'closed_date', 'days_open', 'status'],
                ['hsdes_live_sync_not_configured'],
            ),
            self._chart_binding(
                'daily_new_standard_bug_count',
                'supported_from_seed_facts',
                ['submitted_date', 'HSD_type'],
                ['hsdes_live_sync_not_configured'],
            ),
        ]
        for chart_id in sorted(DEFERRED_CHART_REASONS):
            bindings.append(self._chart_binding(chart_id, 'deferred', [], ['first_wave_deferred_chart']))
        return bindings

    def _chart_binding(self, chart_id: str, support_status: str, candidate_native_fields: list[str], blocker_codes: list[str]) -> dict:
        return {
            'chart_id': chart_id,
            'support_status': support_status,
            'evidence_capability': PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only'),
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

    def _hsdes_drift_items(self, observed_profile: dict) -> list[dict]:
        expected_values = {
            'source_query_ref': FIRST_HSDES_QUERY_ID,
            'tenant_or_site': FIRST_HSDES_TENANT,
            'subject_or_issue_type': FIRST_HSDES_SUBJECT,
            'criteria_snapshot': FIRST_HSDES_CRITERIA_SNAPSHOT,
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
        if observed_field_set != FIRST_HSDES_EXPECTED_FIELD_SET:
            drift_items.append({
                'field': 'field_set',
                'expected': sorted(FIRST_HSDES_EXPECTED_FIELD_SET),
                'observed': sorted(observed_field_set),
            })
        return drift_items

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
