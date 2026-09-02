import sys
from pathlib import Path
from typing import List

from .ai_chart_definitions import AI_CHART_DEFINITIONS
from .ai_dashboard_composition_contracts import (
    AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
    AI_DASHBOARD_MAX_DAYS,
    AI_DASHBOARD_MAX_ROWS,
    AiDashboardValidationFinding,
    DashboardCompositionIntent,
    NeedsMetricRecipe,
    PublicationAuditMetadata,
)
from .provider_aggregate_contracts import PROVIDER_CHART_EVIDENCE_CAPABILITIES
from .provider_profiles import ProviderProfileReadinessService


SCRIPTS_PATH = Path(__file__).resolve().parents[3] / 'scripts'
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from scripts.grafana_artifact_contract import load_allowlist, validate_dashboard_payload, validate_node
from scripts.grafana_render_config import generate_dashboard, validate_render_config


GRAFANA_ALLOWLIST_PATH = Path('openspec/docs/current-baseline/grafana-approved-data-surfaces.json')


class AiDashboardCompositionRules:
    def __init__(self, readiness_service: ProviderProfileReadinessService):
        self._readiness_service = readiness_service

    def list_composition_catalog(self, profile_id: str = '') -> dict:
        profiles = [self._catalog_profile(item) for item in self._catalog_profile_ids(profile_id)]
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'catalog_type': 'profile_catalog',
            'profiles': profiles,
            'chart_recipes': {chart_id: self._catalog_chart_recipe(chart_id, profiles) for chart_id in AI_CHART_DEFINITIONS},
            'range_modes': sorted(self._catalog_range_modes(profiles)),
            'limits': {'max_rows': AI_DASHBOARD_MAX_ROWS, 'max_days': AI_DASHBOARD_MAX_DAYS},
            'security_policy': {
                'provider_credentials_exposed': False,
                'native_query_editing_allowed': False,
                'direct_metrics_code_edits_allowed': False,
                'arbitrary_sql_allowed': False,
                'publication_requires_metrics_precondition': True,
            },
        }

    def validate_composition_intent(self, intent: DashboardCompositionIntent) -> dict:
        findings = self._composition_intent_findings(intent)
        available_series = list(AI_CHART_DEFINITIONS.get(intent.chart_id, {'series': []})['series'])
        unknown_series = sorted(set(intent.requested_series) - set(available_series))
        if unknown_series:
            return self._needs_metric_recipe(intent, available_series, unknown_series, findings)
        if findings:
            return {
                'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
                'valid': False,
                'status': 'validation_failed',
                'findings': [item.to_dict() for item in findings],
            }
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'valid': True,
            'status': 'draft_validated',
            'findings': [],
            'draft_render_config': self.draft_render_config(intent),
            'publication_audit': PublicationAuditMetadata(
                actor=intent.actor,
                operation='render_config_draft',
                validation_status='validated',
                approval_state='approval_required',
                mutation_allowed=False,
            ).to_dict(),
        }

    def validate_render_config_draft(self, draft_render_config: dict) -> dict:
        findings = self.render_config_findings(draft_render_config)
        if findings:
            return {
                'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
                'valid': False,
                'status': 'validation_failed',
                'findings': [item.to_dict() for item in findings],
            }
        dashboard = self.generate_dashboard_from_render_config(draft_render_config)
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'valid': True,
            'status': 'draft_validated',
            'findings': [],
            'dashboard_preview': {
                'dashboard_uid': dashboard.get('uid', ''),
                'title': dashboard.get('title', ''),
                'panel_count': len(dashboard.get('panels', [])),
                'variable_count': len(dashboard.get('templating', {}).get('list', [])),
            },
        }

    def draft_render_config(self, intent: DashboardCompositionIntent) -> dict:
        recipe = load_allowlist(GRAFANA_ALLOWLIST_PATH).provider_chart_recipes[intent.chart_id]
        category_field = sorted(recipe.approved_category_fields)[0]
        evidence_capability = PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(
            intent.chart_id,
            sorted(recipe.approved_evidence_capabilities)[0],
        )
        return {
            'dashboard_uid': intent.dashboard_uid,
            'title': 'AI Draft Dashboard',
            'profile_variable': 'profile_id',
            'variables': [
                {'name': 'profile_id', 'kind': 'profile', 'values': [intent.profile_id], 'current': intent.profile_id},
                {'name': 'range_mode', 'kind': 'constant', 'values': ['ww', 'date'], 'current': intent.range_mode},
                {'name': 'begin_ww', 'type': 'textbox', 'current': intent.range_start if intent.range_mode == 'ww' else '26WW01'},
                {'name': 'end_ww', 'type': 'textbox', 'current': intent.range_end if intent.range_mode == 'ww' else '26WW35'},
            ],
            'range_controls': {
                'mode_variable': 'range_mode',
                'fetch_label': 'Provider Fetch / Cache Window',
                'display_label': 'Display time window',
                'modes': ['ww', 'date'],
            },
            'sections': [{
                'id': 'ai_draft_quality',
                'title': 'AI Draft Quality',
                'layout': {'x': 0, 'y': 0, 'w': 24, 'h': 1},
                'panels': [self._draft_panel(intent, category_field, evidence_capability)],
            }],
        }

    def render_config_findings(self, render_config: dict) -> list[AiDashboardValidationFinding]:
        allowlist = load_allowlist(GRAFANA_ALLOWLIST_PATH)
        findings = validate_node(GRAFANA_ALLOWLIST_PATH, '', render_config, allowlist, None)
        findings.extend(validate_render_config(render_config, allowlist, GRAFANA_ALLOWLIST_PATH))
        if not findings:
            findings.extend(validate_dashboard_payload(GRAFANA_ALLOWLIST_PATH, generate_dashboard(render_config, allowlist), allowlist))
        return [
            AiDashboardValidationFinding('render_config_validation_failed', finding.message, 'error', str(finding.path))
            for finding in findings
        ]

    def generate_dashboard_from_render_config(self, render_config: dict) -> dict:
        return generate_dashboard(render_config, load_allowlist(GRAFANA_ALLOWLIST_PATH))

    def provider_id_for_profile(self, profile_id: str) -> str:
        return self._readiness_service.get_readiness('', profile_id).get('provider_id', '')

    def _needs_metric_recipe(self, intent: DashboardCompositionIntent, available_series: List[str],
                             unknown_series: List[str], findings: list[AiDashboardValidationFinding]) -> dict:
        finding = AiDashboardValidationFinding(
            code='unapproved_series',
            message='Requested series are not approved by the Metrics chart recipe catalog.',
            severity='error',
            field='requested_series',
        )
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'valid': False,
            'status': 'needs_metric_recipe',
            'findings': [item.to_dict() for item in [finding] + findings],
            'needs_metric_recipe': NeedsMetricRecipe(
                chart_id=intent.chart_id,
                requested_series=unknown_series,
                available_series=available_series,
                reason='Metrics must define and validate a new chart recipe or series before AI can render this semantic.',
            ).to_dict(),
        }

    def _catalog_profile_ids(self, profile_id: str) -> List[str]:
        if profile_id:
            return [profile_id]
        return [item['profile_id'] for item in self._readiness_service.list_profile_health()]

    def _catalog_profile(self, profile_id: str) -> dict:
        readiness = self._readiness_service.get_readiness('', profile_id)
        source_population = readiness.get('source_population', {})
        return {
            'profile_id': readiness.get('profile_id', profile_id),
            'provider_id': readiness.get('provider_id', ''),
            'status': readiness.get('status', ''),
            'freshness_status': readiness.get('freshness_status', ''),
            'scope_labels': dict(readiness.get('scope_labels', {})),
            'source_population': self._public_source_population(source_population),
            'mapping_version': readiness.get('mapping_version', ''),
            'mapping_version_hash': readiness.get('mapping_version_hash', ''),
            'chart_support': list(readiness.get('chart_support', [])),
            'range_modes': list(self._profile_range_modes(profile_id)),
        }

    def _public_source_population(self, source_population: dict) -> dict:
        safe_keys = (
            'ownership_type',
            'source_query_ref',
            'source_query_name',
            'source_query_hash',
            'tenant_or_site',
            'subject_or_issue_type',
            'criteria_operator',
            'mapping_version',
            'mapping_version_hash',
        )
        return {key: source_population.get(key, '') for key in safe_keys if source_population.get(key, '') != ''}

    def _catalog_chart_recipe(self, chart_id: str, profiles: list[dict]) -> dict:
        definition = AI_CHART_DEFINITIONS[chart_id]
        return {
            'chart_id': chart_id,
            'chart_version': 1,
            'title': definition['title'],
            'semantic_owner': 'metrics',
            'allowed_series': list(definition['series']),
            'data_surface': '/api/provider-charts/data/',
            'evidence_capability': PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only'),
            'support_status': self._catalog_chart_support_status(chart_id, profiles),
        }

    def _catalog_chart_support_status(self, chart_id: str, profiles: list[dict]) -> str:
        statuses = [
            binding.get('support_status', '')
            for profile in profiles
            for binding in profile.get('chart_support', [])
            if binding.get('chart_id') == chart_id
        ]
        if not statuses:
            return 'unsupported'
        if 'supported' in statuses:
            return 'supported'
        if 'deferred' in statuses:
            return 'deferred'
        return statuses[0]

    def _catalog_range_modes(self, profiles: list[dict]) -> set[str]:
        range_modes = {range_mode for profile in profiles for range_mode in profile.get('range_modes', [])}
        return range_modes or {'ww'}

    def _profile_range_modes(self, profile_id: str) -> List[str]:
        try:
            profile = self._readiness_service._profile_registry.get_profile(profile_id)
        except KeyError:
            return []
        return list(profile.sync_policy.get('range_modes', ['ww']))

    def _composition_intent_findings(self, intent: DashboardCompositionIntent) -> list[AiDashboardValidationFinding]:
        findings = []
        readiness = self._readiness_service.get_readiness('', intent.profile_id)
        if readiness.get('status') in {'unsupported', 'unavailable'}:
            findings.append(AiDashboardValidationFinding('profile_not_available', 'Selected profile is not available.', 'error', 'profile_id'))
        if intent.chart_id not in AI_CHART_DEFINITIONS:
            findings.append(AiDashboardValidationFinding('unknown_chart_recipe', 'Requested chart is not approved by the Metrics catalog.', 'error', 'chart_id'))
        elif self._catalog_chart_support_status(intent.chart_id, [self._catalog_profile(intent.profile_id)]) != 'supported':
            findings.append(AiDashboardValidationFinding('chart_not_supported_for_profile', 'Requested chart is not supported by the selected profile.', 'error', 'chart_id'))
        if intent.range_mode not in self._profile_range_modes(intent.profile_id):
            findings.append(AiDashboardValidationFinding('unsupported_range_mode', 'Requested range mode is not enabled for the selected profile.', 'error', 'range_mode'))
        if intent.output_type != 'render_config_draft':
            findings.append(AiDashboardValidationFinding('unsupported_output_type', 'AI dashboard composition currently supports render config drafts only.', 'error', 'output_type'))
        return findings

    def _draft_panel(self, intent: DashboardCompositionIntent, category_field: str, evidence_capability: str) -> dict:
        return {
            'panel_id': '1',
            'title': intent.panel_title or AI_CHART_DEFINITIONS[intent.chart_id]['title'],
            'type': intent.visualization,
            'layout': {'x': 0, 'y': 1, 'w': 12, 'h': 8},
            'chart_recipe_ref': {'chart_id': intent.chart_id, 'chart_version': 1},
            'provider_binding': 'selected_provider_quality',
            'render_root': 'grafana_rows',
            'render_shape': 'wide_bucket_series',
            'category_field': category_field,
            'value_fields': list(intent.requested_series),
            'evidence_capability': evidence_capability,
            'evidence_link': {'enabled': evidence_capability == 'bucket_series', 'fields': ['calculation_run_id', 'bucket_id']},
        }
