from .ai_dashboard_composition_rules import AiDashboardCompositionRules
from .provider_profiles import ProviderProfileReadinessService


class ProviderAiDashboardContextService:
    def __init__(self, aggregate_service, readiness_service: ProviderProfileReadinessService | None = None):
        self._readiness_service = readiness_service or ProviderProfileReadinessService()
        self._composition_rules = AiDashboardCompositionRules(self._readiness_service)

    def list_composition_catalog(self, profile_id: str = '') -> dict:
        return self._composition_rules.list_composition_catalog(profile_id)

    def get_workbench_context(self, values: dict) -> dict:
        profile_id = values['profile_id']
        readiness = self._readiness_service.get_readiness('', profile_id)
        provider_id = readiness.get('provider_id', '')
        scope_labels = readiness.get('scope_labels', {})
        mapping_hash = readiness.get('mapping_version_hash', '')
        if provider_id != values['provider_id'] or readiness.get('status') in {'unsupported', 'disabled'}:
            return {'status': 'binding_unresolved'}
        boundary = {
            'binding_key': values['binding_key'],
            'allowed_provider_ids': [provider_id] if provider_id else [],
            'allowed_profile_ids': [profile_id],
            'project_labels': scope_labels,
            'range_modes': self._profile_range_modes(readiness),
            'permitted_data_block_ids': ['work_item.quality_facts', 'work_item.weekly_quality_buckets'],
        }
        provider_profile = {
            'provider_id': provider_id,
            'profile_id': profile_id,
            'status': readiness.get('status', ''),
            'freshness_status': readiness.get('freshness_status', ''),
            'mapping_version': readiness.get('mapping_version', ''),
            'mapping_version_hash': mapping_hash,
            'scope_labels': scope_labels,
            'source_population': self._safe_source_population(readiness.get('source_population', {})),
        }
        files = [
            self._json_bundle_file('metrics-context/context-boundary.json', boundary, 'context_boundary', 'model_context'),
            self._json_bundle_file('metrics-context/provider-profile.json', provider_profile, 'provider_profile', 'model_context'),
            self._json_bundle_file('metrics-context/canonical-field-map.json', self._canonical_field_map(provider_id), 'canonical_field_map', 'model_context'),
            self._json_bundle_file('metrics-context/data-block-catalog.json', self._data_block_catalog(provider_id, profile_id, scope_labels), 'data_block_catalog', 'model_context'),
            self._json_bundle_file('metrics-context/grafana-render-contract.json', self._grafana_render_contract(), 'grafana_render_contract', 'catalog_only'),
            {
                'path': 'metrics-context/metrics-help.md',
                'content_type': 'text/markdown',
                'content_text': self._metrics_context_help(profile_id, provider_id),
                'visibility': 'model_context',
                'role': 'metrics_help',
            },
        ]
        return {
            'status': 'ready',
            'context_ref': {'kind': 'metrics.workbench', 'values': dict(values)},
            'bundle_version': f"{profile_id}:{mapping_hash or 'unmapped'}",
            'boundary': boundary,
            'files': files,
        }

    def _profile_range_modes(self, readiness: dict) -> list[str]:
        source = readiness.get('source_population', {})
        if source.get('provider_id') in {'jira', 'hsdes'} or readiness.get('provider_id') in {'jira', 'hsdes'}:
            return ['date', 'ww']
        return ['ww']

    def _safe_source_population(self, source_population: dict) -> dict:
        safe_keys = (
            'profile_id',
            'provider_id',
            'ownership_type',
            'source_query_ref',
            'source_query_name',
            'source_query_hash',
            'tenant_or_site',
            'subject_or_issue_type',
            'criteria_operator',
            'mapping_version',
            'mapping_version_hash',
            'fact_snapshot_id',
        )
        return {key: source_population.get(key, '') for key in safe_keys if source_population.get(key, '') != ''}

    def _canonical_field_map(self, provider_id: str) -> dict:
        provider_examples = {
            'jira': {
                'work_item_id': 'issue.key',
                'title': 'summary',
                'status': 'status',
                'severity': 'priority',
                'owner': 'assignee',
                'component': 'components',
                'created_at': 'created',
                'updated_at': 'updated',
                'closed_at': 'resolutiondate',
                'milestone': 'fixVersions',
                'project': 'project',
                'ip': 'project_config.ip',
                'source_url': 'browse_url',
            },
            'hsdes': {
                'work_item_id': 'id',
                'title': 'title',
                'status': 'status',
                'severity': 'priority',
                'owner': 'owner',
                'component': 'component',
                'created_at': 'submitted_date',
                'updated_at': 'updated_date',
                'closed_at': 'closed_date',
                'milestone': 'release',
                'project': 'family',
                'ip': 'tenant',
                'source_url': 'article_url',
            },
        }
        return {
            'schema_version': '0.1',
            'field_policy': 'AI and Grafana artifacts must use canonical field names; provider-native names are provenance only.',
            'canonical_fields': list(self._quality_fact_fields()),
            'provider_field_examples': provider_examples.get(provider_id, {}),
        }

    def _data_block_catalog(self, provider_id: str, profile_id: str, scope_labels: dict) -> dict:
        return {
            'schema_version': '0.1',
            'provider_id': provider_id,
            'profile_id': profile_id,
            'data_blocks': [
                {
                    'block_id': 'work_item.quality_facts',
                    'grain': 'item',
                    'canonical_fields': list(self._quality_fact_fields()),
                    'dimensions': ['status', 'severity', 'owner', 'component', 'milestone', 'project', 'ip'],
                    'measures': ['item_count'],
                    'allowed_transforms': ['filter', 'group_by', 'count', 'top_n'],
                    'evidence_capability': 'item_rows',
                    'scope_labels': scope_labels,
                },
                {
                    'block_id': 'work_item.weekly_quality_buckets',
                    'grain': 'week',
                    'canonical_fields': [
                        'bucket_ww',
                        'bucket_start',
                        'bucket_end',
                        'severity',
                        'component',
                        'owner',
                        'status',
                    ],
                    'dimensions': ['bucket_ww', 'severity', 'component', 'owner', 'status'],
                    'measures': ['all_open_bugs', 'all_open_critical_high', 'new_critical_high', 'new_medium_low', 'fixed_or_closed_bugs'],
                    'allowed_transforms': ['filter', 'group_by', 'sum', 'trend', 'pivot'],
                    'evidence_capability': 'bucket_series',
                    'scope_labels': scope_labels,
                },
            ],
        }

    def _grafana_render_contract(self) -> dict:
        return {
            'schema_version': '0.1',
            'allowed_datasource_uid': 'metrics-bug-trend-api',
            'allowed_panel_types': ['barchart', 'timeseries', 'table', 'stat'],
            'allowed_data_roots': ['grafana_rows', 'provider_series_state'],
            'publish_policy': 'Metrics validation and approval required before Grafana import.',
        }

    def _metrics_context_help(self, profile_id: str, provider_id: str) -> str:
        return (
            f"# Metrics workbench context\n\n"
            f"This context is bounded to provider `{provider_id}` and profile `{profile_id}`.\n\n"
            "Use canonical field names from `canonical-field-map.json` and data blocks from "
            "`data-block-catalog.json`. Do not use provider-native fields in generated artifacts."
        )

    def _quality_fact_fields(self) -> tuple[str, ...]:
        return (
            'work_item_id',
            'title',
            'status',
            'severity',
            'priority',
            'owner',
            'component',
            'created_at',
            'updated_at',
            'closed_at',
            'milestone',
            'project',
            'ip',
            'source_url',
        )

    def _json_bundle_file(self, path: str, content: dict, role: str, visibility: str) -> dict:
        return {
            'path': path,
            'content_type': 'application/json',
            'content_json': content,
            'visibility': visibility,
            'role': role,
        }
