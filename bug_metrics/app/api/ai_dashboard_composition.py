from pathlib import Path
import sys
from typing import List
from datetime import date, timedelta
import base64
import json
import re
import urllib.parse
import urllib.request

from django.conf import settings

from bug_metrics.models import BugTrendAuditEvent

SCRIPTS_PATH = Path(__file__).resolve().parents[3] / 'scripts'
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from scripts.grafana_artifact_contract import load_allowlist, validate_dashboard_payload, validate_node
from scripts.grafana_render_config import generate_dashboard, validate_render_config

from .ai_chart_definitions import AI_CHART_DEFINITIONS
from .ai_dashboard_composition_contracts import (
    AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
    AI_DASHBOARD_MAX_DAYS,
    AI_DASHBOARD_MAX_ROWS,
    AiDashboardValidationFinding,
    DashboardAiArtifactValidationRequest,
    DashboardAiPublishRequest,
    DashboardCompositionIntent,
    GcxPublicationCallbackRequest,
    GcxPublicationPreconditionRequest,
    NeedsMetricRecipe,
    PublicationAuditMetadata,
)
from .provider_aggregate_contracts import PROVIDER_CHART_EVIDENCE_CAPABILITIES
from .provider_profiles import ProviderProfileReadinessService


GRAFANA_ALLOWLIST_PATH = Path('openspec/docs/current-baseline/grafana-approved-data-surfaces.json')


class AiDashboardCompositionService:
    def __init__(self, readiness_service: ProviderProfileReadinessService | None = None):
        self._readiness_service = readiness_service or ProviderProfileReadinessService()

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
            'draft_render_config': self._draft_render_config(intent),
            'publication_audit': PublicationAuditMetadata(
                actor=intent.actor,
                operation='render_config_draft',
                validation_status='validated',
                approval_state='approval_required',
                mutation_allowed=False,
            ).to_dict(),
        }

    def validate_render_config_draft(self, draft_render_config: dict) -> dict:
        findings = self._render_config_findings(draft_render_config)
        if findings:
            return {
                'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
                'valid': False,
                'status': 'validation_failed',
                'findings': [item.to_dict() for item in findings],
            }
        allowlist = load_allowlist(GRAFANA_ALLOWLIST_PATH)
        dashboard = generate_dashboard(draft_render_config, allowlist)
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

    def validate_workspace_artifact(self, request: DashboardAiArtifactValidationRequest) -> dict:
        self._validate_artifact_metadata(request)
        artifact = request.artifact
        unsafe_findings = self._artifact_content_findings(artifact)
        if unsafe_findings:
            return {
                'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
                'artifact_ref': request.artifact_ref,
                'artifact_version': request.artifact_version,
                'workspace_key': request.workspace_key,
                'correlation_id': request.correlation_id,
                'valid': False,
                'status': 'validation_failed',
                'intent_validation': {'status': 'not_checked', 'valid': False, 'findings': []},
                'findings': [item.to_dict() for item in unsafe_findings],
            }
        intent = DashboardCompositionIntent(
            profile_id=str(artifact['profile_id']),
            dashboard_uid=str(artifact['dashboard_uid']),
            chart_id=str(artifact.get('chart_id', 'open_bug_trend')),
            requested_series=list(artifact.get('requested_series', [])),
            range_mode=str(artifact.get('range_mode', 'ww')),
            range_start=str(artifact.get('range_start', artifact.get('begin_ww', ''))),
            range_end=str(artifact.get('range_end', artifact.get('end_ww', ''))),
            output_type=str(artifact.get('output_type', 'render_config_draft')),
            actor=request.actor,
            panel_title=str(artifact.get('panel_title', '')),
            visualization=str(artifact.get('visualization', 'timeseries')),
        )
        intent_validation = self.validate_composition_intent(intent)
        if intent_validation.get('status') == 'needs_metric_recipe':
            return self._artifact_validation_result(request, False, 'needs_metric_recipe', intent_validation)
        if not intent_validation.get('valid'):
            return self._artifact_validation_result(request, False, 'validation_failed', intent_validation)
        render_config = artifact.get('draft_render_config') or intent_validation.get('draft_render_config')
        render_validation = self.validate_render_config_draft(render_config)
        if not render_validation.get('valid'):
            result = self._artifact_validation_result(request, False, 'validation_failed', intent_validation)
            result['render_validation'] = render_validation
            return result
        return {
            **self._artifact_validation_result(request, True, 'draft_validated', intent_validation),
            'render_validation': render_validation,
            'normalized_render_config': render_config,
        }

    def validate_gcx_publication_precondition(self, request: GcxPublicationPreconditionRequest) -> dict:
        findings = self._gcx_operation_findings(request) + self._render_config_findings(request.draft_render_config)
        if findings:
            return self._blocked_precondition(request, findings)
        BugTrendAuditEvent.objects.create(
            event_type='ai_gcx_publication_precondition_passed',
            actor=request.actor,
            request_summary={
                'operation': request.operation,
                'dashboard_uid': request.draft_render_config.get('dashboard_uid', ''),
                'approval_policy': request.approval_policy,
            },
        )
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'status': 'precondition_passed',
            'mutation_allowed': True,
            'findings': [],
            'publication_audit': PublicationAuditMetadata(
                actor=request.actor,
                operation=request.operation,
                validation_status='validated',
                approval_state=request.approval_policy,
                mutation_allowed=True,
            ).to_dict(),
        }

    def record_gcx_publication_callback(self, request: GcxPublicationCallbackRequest) -> dict:
        if not request.dashboard_uid:
            raise ValueError('dashboard_uid is required.')
        if not request.correlation_id:
            raise ValueError('correlation_id is required.')
        BugTrendAuditEvent.objects.create(
            event_type='ai_gcx_publication_callback_recorded',
            actor=request.actor,
            request_summary={
                'operation': request.operation,
                'dashboard_uid': request.dashboard_uid,
                'artifact_ref': request.artifact_ref,
                'mutation_status': request.mutation_status,
                'correlation_id': request.correlation_id,
                'dry_run_proof_id': request.dry_run_proof_id,
            },
            result=request.mutation_status,
        )
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'status': 'recorded',
            'operation': request.operation,
            'dashboard_uid': request.dashboard_uid,
            'mutation_status': request.mutation_status,
            'correlation_id': request.correlation_id,
        }

    def publish_grafana_dashboard_demo(self, request: DashboardAiPublishRequest, correlation_id: str) -> dict:
        if not request.approval_id:
            raise ValueError('approval_id is required.')
        if not request.dry_run_proof_id:
            raise ValueError('dry_run_proof_id is required.')
        intent_validation = self.validate_composition_intent(
            DashboardCompositionIntent(
                profile_id=request.profile_id,
                dashboard_uid=request.dashboard_uid,
                chart_id=request.chart_id,
                requested_series=list(request.requested_series),
                range_mode=request.range_mode,
                range_start=request.range_start,
                range_end=request.range_end,
                output_type=request.output_type,
                actor=request.actor,
                panel_title=request.panel_title,
                visualization=request.visualization,
            )
        )
        draft_render_config = intent_validation.get('draft_render_config')
        if not draft_render_config:
            return self._blocked_publish_result(request, correlation_id, intent_validation, 'intent_validation_blocked')
        render_validation = self.validate_render_config_draft(draft_render_config)
        if not render_validation.get('valid'):
            return self._blocked_publish_result(request, correlation_id, render_validation, 'render_validation_blocked')
        precondition = self.validate_gcx_publication_precondition(
            GcxPublicationPreconditionRequest(
                operation=request.operation,
                actor=request.actor,
                draft_render_config=draft_render_config,
            )
        )
        if not precondition.get('mutation_allowed'):
            return self._blocked_publish_result(request, correlation_id, precondition, 'precondition_blocked')
        allowlist = load_allowlist(GRAFANA_ALLOWLIST_PATH)
        dashboard = generate_dashboard(draft_render_config, allowlist)
        dashboard['time'] = self._grafana_time_range(request)
        dashboard['timezone'] = 'browser'
        grafana_base_url = self._configured_grafana_base_url()
        import_result = import_grafana_dashboard_payload(
            grafana_base_url,
            dashboard,
            str(settings.METRICS_AI_GRAFANA_USERNAME),
            str(settings.METRICS_AI_GRAFANA_PASSWORD),
        )
        artifact_ref = request.artifact_ref or f'grafana://{request.dashboard_uid}'
        audit = self.record_gcx_publication_callback(
            GcxPublicationCallbackRequest(
                operation=request.operation,
                actor=request.actor,
                dashboard_uid=request.dashboard_uid,
                artifact_ref=artifact_ref,
                mutation_status='succeeded',
                correlation_id=correlation_id,
                dry_run_proof_id=request.dry_run_proof_id,
            )
        )
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'status': 'published',
            'operation': request.operation,
            'provider_id': self._provider_id_for_profile(request.profile_id),
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'chart_version': 1,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'visualization': request.visualization,
            'dashboard_url': self._grafana_dashboard_url(grafana_base_url, request),
            'correlation_id': correlation_id,
            'dry_run_proof_id': request.dry_run_proof_id,
            'approval_id': request.approval_id,
            'artifact_ref': artifact_ref,
            'artifact_version': request.artifact_version,
            'import_result': import_result,
            'audit': audit,
        }

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

    def _blocked_precondition(self, request: GcxPublicationPreconditionRequest,
                              findings: list[AiDashboardValidationFinding]) -> dict:
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'status': 'blocked',
            'mutation_allowed': False,
            'findings': [item.to_dict() for item in findings],
            'publication_audit': PublicationAuditMetadata(
                actor=request.actor,
                operation=request.operation,
                validation_status='metrics_precondition_failed',
                approval_state='blocked',
                mutation_allowed=False,
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

    def _draft_render_config(self, intent: DashboardCompositionIntent) -> dict:
        recipe = load_allowlist(GRAFANA_ALLOWLIST_PATH).provider_chart_recipes[intent.chart_id]
        category_field = sorted(recipe.approved_category_fields)[0]
        evidence_capability = PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(intent.chart_id, sorted(recipe.approved_evidence_capabilities)[0])
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

    def _gcx_operation_findings(self, request: GcxPublicationPreconditionRequest) -> list[AiDashboardValidationFinding]:
        approved_operations = {'grafana_validate', 'grafana_import', 'grafana_snapshot', 'grafana_publish'}
        if request.operation in approved_operations:
            return []
        return [AiDashboardValidationFinding('unsupported_gcx_operation', 'gcx operation is not approved by Metrics.', 'error', 'operation')]

    def _blocked_publish_result(self, request: DashboardAiPublishRequest, correlation_id: str, validation: dict, reason: str) -> dict:
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'status': 'blocked',
            'reason': reason,
            'operation': request.operation,
            'dashboard_uid': request.dashboard_uid,
            'correlation_id': correlation_id,
            'dry_run_proof_id': request.dry_run_proof_id,
            'approval_id': request.approval_id,
            'validation': validation,
        }

    def _validate_artifact_metadata(self, request: DashboardAiArtifactValidationRequest) -> None:
        if not request.artifact_ref:
            raise ValueError('artifact_ref is required.')
        if request.artifact_version < 1:
            raise ValueError('artifact_version must be positive.')
        if not request.workspace_key:
            raise ValueError('workspace_key is required.')
        if not request.correlation_id:
            raise ValueError('correlation_id is required.')
        if not isinstance(request.artifact, dict):
            raise ValueError('artifact must be an object.')
        missing = [field for field in ('profile_id', 'dashboard_uid') if not request.artifact.get(field)]
        if missing:
            raise ValueError(f'artifact missing required fields: {", ".join(missing)}.')

    def _artifact_validation_result(self, request: DashboardAiArtifactValidationRequest, valid: bool, status: str, intent_validation: dict) -> dict:
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'artifact_ref': request.artifact_ref,
            'artifact_version': request.artifact_version,
            'workspace_key': request.workspace_key,
            'correlation_id': request.correlation_id,
            'valid': valid,
            'status': status,
            'intent_validation': intent_validation,
            'findings': list(intent_validation.get('findings', [])),
        }

    def _artifact_content_findings(self, value, path: str = 'artifact') -> list[AiDashboardValidationFinding]:
        findings = []
        if isinstance(value, dict):
            for key, item in value.items():
                field_path = f'{path}.{key}'
                if self._is_sensitive_artifact_key(str(key)):
                    findings.append(AiDashboardValidationFinding(
                        'unsafe_artifact_content',
                        'AI workspace artifact contains provider-native, secret-like or private-path content.',
                        'error',
                        field_path,
                    ))
                else:
                    findings.extend(self._artifact_content_findings(item, field_path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                findings.extend(self._artifact_content_findings(item, f'{path}[{index}]'))
        return findings

    def _is_sensitive_artifact_key(self, key: str) -> bool:
        normalized = key.lower()
        compact = ''.join(character for character in normalized if character.isalnum())
        fragments = ('password', 'token', 'secret', 'apikey', 'privatepath', 'nativequerytext', 'rawquery', 'providernativequery')
        return normalized == 'sql' or any(fragment in compact for fragment in fragments)

    def _provider_id_for_profile(self, profile_id: str) -> str:
        return self._readiness_service.get_readiness('', profile_id).get('provider_id', '')

    def _grafana_dashboard_url(self, grafana_base_url: str, request: DashboardAiPublishRequest) -> str:
        query_values = {
            'orgId': '1',
            'var-profile_id': request.profile_id,
            'var-range_mode': request.range_mode,
            'var-begin_ww': request.range_start if request.range_mode == 'ww' else '',
            'var-end_ww': request.range_end if request.range_mode == 'ww' else '',
            **self._grafana_time_range(request),
            'timezone': 'browser',
        }
        query = urllib.parse.urlencode({key: value for key, value in query_values.items() if value})
        return f'{grafana_base_url}/d/{request.dashboard_uid}/ai-draft-dashboard?{query}'

    def _configured_grafana_base_url(self) -> str:
        configured = str(settings.METRICS_AI_GRAFANA_BASE_URL).rstrip('/')
        if configured != 'http://127.0.0.1:3001':
            return configured
        summary_path = Path(settings.METRICS_STATE_DIR) / 'e2e' / 'bug_trend_ports.json'
        if not summary_path.exists():
            return configured
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        grafana_port = summary.get('grafana_port')
        if not isinstance(grafana_port, int):
            return configured
        return f'http://127.0.0.1:{grafana_port}'

    def _grafana_time_range(self, request: DashboardAiPublishRequest) -> dict:
        if request.range_mode == 'ww':
            begin, end = self._ww_range_to_dates(request.range_start, request.range_end)
            return {'from': f'{begin.isoformat()}T00:00:00', 'to': f'{end.isoformat()}T23:59:59'}
        return {'from': request.range_start, 'to': request.range_end}

    def _ww_range_to_dates(self, begin_ww: str, end_ww: str) -> tuple[date, date]:
        begin = self._ww_to_monday(begin_ww)
        end = self._ww_to_monday(end_ww) + timedelta(days=6)
        if begin > end:
            raise ValueError('range_start must be earlier than or equal to range_end.')
        return begin, end

    def _ww_to_monday(self, value: str) -> date:
        normalized = value.strip()
        if not re.fullmatch(r'\d{2}WW\d{2}', normalized, flags=re.IGNORECASE):
            raise ValueError('WW values must use YYWWNN format.')
        return date.fromisocalendar(2000 + int(normalized[:2]), int(normalized[4:]), 1)

    def _render_config_findings(self, render_config: dict) -> list[AiDashboardValidationFinding]:
        allowlist = load_allowlist(GRAFANA_ALLOWLIST_PATH)
        findings = validate_node(GRAFANA_ALLOWLIST_PATH, '', render_config, allowlist, None)
        findings.extend(validate_render_config(render_config, allowlist, GRAFANA_ALLOWLIST_PATH))
        if not findings:
            findings.extend(validate_dashboard_payload(GRAFANA_ALLOWLIST_PATH, generate_dashboard(render_config, allowlist), allowlist))
        return [
            AiDashboardValidationFinding('render_config_validation_failed', finding.message, 'error', str(finding.path))
            for finding in findings
        ]


def import_grafana_dashboard_payload(grafana_base_url: str, dashboard: dict, username: str, password: str) -> dict:
    payload = json.dumps({
        'dashboard': dashboard,
        'overwrite': True,
        'message': 'Approved AI Dashboard local demo publish',
    }).encode('utf-8')
    request = urllib.request.Request(f'{grafana_base_url}/api/dashboards/db', data=payload, method='POST')
    request.add_header('Content-Type', 'application/json')
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    request.add_header('Authorization', f'Basic {token}')
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))
