from dataclasses import dataclass
from typing import List


AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION = '0.2'
AI_DASHBOARD_MAX_ROWS = 500
AI_DASHBOARD_MAX_DAYS = 370


@dataclass(frozen=True, slots=True)
class DashboardCompositionIntent:
    profile_id: str
    dashboard_uid: str
    chart_id: str
    requested_series: List[str]
    range_mode: str
    range_start: str
    range_end: str
    output_type: str
    actor: str = 'local_operator'
    panel_title: str = ''
    visualization: str = 'timeseries'


@dataclass(frozen=True, slots=True)
class DashboardAiWorkflowRequest:
    profile_id: str
    dashboard_uid: str
    chart_id: str
    requested_series: List[str]
    range_mode: str
    range_start: str
    range_end: str
    operation: str = 'grafana_import'
    actor: str = 'local_operator'
    output_type: str = 'render_config_draft'
    panel_title: str = ''
    visualization: str = 'timeseries'


@dataclass(frozen=True, slots=True)
class DashboardAiPublishRequest:
    profile_id: str
    dashboard_uid: str
    chart_id: str
    requested_series: List[str]
    range_mode: str
    range_start: str
    range_end: str
    operation: str
    actor: str
    approval_id: str
    dry_run_proof_id: str
    output_type: str = 'render_config_draft'
    panel_title: str = ''
    visualization: str = 'timeseries'
    artifact_ref: str = ''
    artifact_version: int = 0
    artifact_hash: str = ''
    provider_id: str = ''
    workspace_key: str = ''


@dataclass(frozen=True, slots=True)
class DashboardAiArtifactValidationRequest:
    artifact_ref: str
    artifact_version: int
    workspace_key: str
    correlation_id: str
    artifact: dict
    actor: str = 'ai_sidecar'


@dataclass(frozen=True, slots=True)
class DashboardAiPublishApprovalRequest:
    profile_id: str
    dashboard_uid: str
    chart_id: str
    requested_series: List[str]
    range_mode: str
    range_start: str
    range_end: str
    dry_run_proof_id: str
    actor: str = 'local_operator'
    artifact_ref: str = ''
    artifact_version: int = 0
    artifact_hash: str = ''
    operation: str = 'grafana_import'
    provider_id: str = ''
    workspace_key: str = ''


@dataclass(frozen=True, slots=True)
class GcxPublicationPreconditionRequest:
    operation: str
    actor: str
    draft_render_config: dict
    approval_policy: str = 'approval_required'


@dataclass(frozen=True, slots=True)
class GcxPublicationCallbackRequest:
    operation: str
    actor: str
    dashboard_uid: str
    artifact_ref: str
    mutation_status: str
    correlation_id: str
    dry_run_proof_id: str


@dataclass(frozen=True, slots=True)
class AiDashboardValidationFinding:
    code: str
    message: str
    severity: str
    field: str

    def to_dict(self) -> dict:
        return {
            'code': self.code,
            'message': self.message,
            'severity': self.severity,
            'field': self.field,
        }


@dataclass(frozen=True, slots=True)
class NeedsMetricRecipe:
    chart_id: str
    requested_series: List[str]
    available_series: List[str]
    reason: str

    def to_dict(self) -> dict:
        return {
            'chart_id': self.chart_id,
            'requested_series': list(self.requested_series),
            'available_series': list(self.available_series),
            'reason': self.reason,
        }


@dataclass(frozen=True, slots=True)
class PublicationAuditMetadata:
    actor: str
    operation: str
    validation_status: str
    approval_state: str
    mutation_allowed: bool

    def to_dict(self) -> dict:
        return {
            'actor': self.actor,
            'operation': self.operation,
            'validation_status': self.validation_status,
            'approval_state': self.approval_state,
            'mutation_allowed': self.mutation_allowed,
        }
