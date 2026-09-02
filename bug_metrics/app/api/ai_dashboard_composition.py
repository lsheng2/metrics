from django.conf import settings

from bug_metrics.models import BugTrendAuditEvent

from .ai_dashboard_artifact_validation import AiDashboardArtifactValidator
from .ai_dashboard_composition_contracts import (
    AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
    AiDashboardValidationFinding,
    DashboardAiArtifactValidationRequest,
    DashboardAiPublishRequest,
    DashboardCompositionIntent,
    GcxPublicationCallbackRequest,
    GcxPublicationPreconditionRequest,
    PublicationAuditMetadata,
)
from .ai_dashboard_composition_rules import AiDashboardCompositionRules
from .ai_dashboard_grafana_publish import configured_grafana_base_url, grafana_dashboard_url, grafana_time_range
from .ai_dashboard_grafana_publish import import_grafana_dashboard_payload
from .provider_profiles import ProviderProfileReadinessService


class AiDashboardCompositionService:
    def __init__(self, readiness_service: ProviderProfileReadinessService | None = None):
        self._readiness_service = readiness_service or ProviderProfileReadinessService()
        self._rules = AiDashboardCompositionRules(self._readiness_service)
        self._artifact_validator = AiDashboardArtifactValidator(self._rules)

    def list_composition_catalog(self, profile_id: str = '') -> dict:
        return self._rules.list_composition_catalog(profile_id)

    def validate_composition_intent(self, intent: DashboardCompositionIntent) -> dict:
        return self._rules.validate_composition_intent(intent)

    def validate_render_config_draft(self, draft_render_config: dict) -> dict:
        return self._rules.validate_render_config_draft(draft_render_config)

    def validate_workspace_artifact(self, request: DashboardAiArtifactValidationRequest) -> dict:
        return self._artifact_validator.validate_workspace_artifact(request)

    def validate_gcx_publication_precondition(self, request: GcxPublicationPreconditionRequest) -> dict:
        findings = self._gcx_operation_findings(request) + self._rules.render_config_findings(request.draft_render_config)
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
        dashboard = self._rules.generate_dashboard_from_render_config(draft_render_config)
        dashboard['time'] = grafana_time_range(request)
        dashboard['timezone'] = 'browser'
        grafana_base_url = configured_grafana_base_url()
        import_result = import_grafana_dashboard_payload(
            grafana_base_url,
            dashboard,
            str(settings.METRICS_AI_GRAFANA_USERNAME),
            str(settings.METRICS_AI_GRAFANA_PASSWORD),
        )
        artifact_ref = request.artifact_ref or f'grafana://{request.dashboard_uid}'
        provider_id = self._rules.provider_id_for_profile(request.profile_id)
        workspace_key = request.workspace_key or f'metrics.{provider_id}.{request.profile_id}'
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
            'provider_id': provider_id,
            'profile_id': request.profile_id,
            'dashboard_uid': request.dashboard_uid,
            'chart_id': request.chart_id,
            'chart_version': 1,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'visualization': request.visualization,
            'dashboard_url': grafana_dashboard_url(grafana_base_url, request),
            'correlation_id': correlation_id,
            'dry_run_proof_id': request.dry_run_proof_id,
            'approval_id': request.approval_id,
            'artifact_ref': artifact_ref,
            'artifact_version': request.artifact_version,
            'artifact_hash': request.artifact_hash,
            'workspace_key': workspace_key,
            'import_result': import_result,
            'audit': audit,
        }

    def _gcx_operation_findings(self, request: GcxPublicationPreconditionRequest) -> list[AiDashboardValidationFinding]:
        approved_operations = {'grafana_validate', 'grafana_import', 'grafana_snapshot', 'grafana_publish'}
        if request.operation in approved_operations:
            return []
        return [AiDashboardValidationFinding('unsupported_gcx_operation', 'gcx operation is not approved by Metrics.', 'error', 'operation')]

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

    def _blocked_publish_result(self, request: DashboardAiPublishRequest, correlation_id: str,
                                validation: dict, reason: str) -> dict:
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
