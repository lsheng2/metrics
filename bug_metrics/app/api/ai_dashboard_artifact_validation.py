from .ai_dashboard_composition_contracts import (
    AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
    AiDashboardValidationFinding,
    DashboardAiArtifactValidationRequest,
    DashboardCompositionIntent,
)
from .ai_dashboard_composition_rules import AiDashboardCompositionRules


class AiDashboardArtifactValidator:
    def __init__(self, rules: AiDashboardCompositionRules):
        self._rules = rules

    def validate_workspace_artifact(self, request: DashboardAiArtifactValidationRequest) -> dict:
        self._validate_artifact_metadata(request)
        artifact = request.artifact
        boundary_findings = self._artifact_workspace_boundary_findings(request)
        if boundary_findings:
            return self._not_checked_result(request, boundary_findings)
        unsafe_findings = self._artifact_content_findings(artifact)
        if unsafe_findings:
            return self._not_checked_result(request, unsafe_findings)
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
        intent_validation = self._rules.validate_composition_intent(intent)
        if intent_validation.get('status') == 'needs_metric_recipe':
            return self._artifact_validation_result(request, False, 'needs_metric_recipe', intent_validation)
        if not intent_validation.get('valid'):
            return self._artifact_validation_result(request, False, 'validation_failed', intent_validation)
        render_config = artifact.get('draft_render_config') or intent_validation.get('draft_render_config')
        render_validation = self._rules.validate_render_config_draft(render_config)
        if not render_validation.get('valid'):
            result = self._artifact_validation_result(request, False, 'validation_failed', intent_validation)
            result['render_validation'] = render_validation
            return result
        return {
            **self._artifact_validation_result(request, True, 'draft_validated', intent_validation),
            'render_validation': render_validation,
            'normalized_render_config': render_config,
        }

    def _not_checked_result(self, request: DashboardAiArtifactValidationRequest,
                            findings: list[AiDashboardValidationFinding]) -> dict:
        return {
            'contract_version': AI_DASHBOARD_COMPOSITION_CONTRACT_VERSION,
            'artifact_ref': request.artifact_ref,
            'artifact_version': request.artifact_version,
            'workspace_key': request.workspace_key,
            'correlation_id': request.correlation_id,
            'valid': False,
            'status': 'validation_failed',
            'intent_validation': {'status': 'not_checked', 'valid': False, 'findings': []},
            'findings': [item.to_dict() for item in findings],
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

    def _artifact_workspace_boundary_findings(self, request: DashboardAiArtifactValidationRequest) -> list[AiDashboardValidationFinding]:
        profile_id = str(request.artifact.get('profile_id', ''))
        provider_id = self._rules.provider_id_for_profile(profile_id)
        expected_workspace_key = f'metrics.{provider_id}.{profile_id}' if provider_id and profile_id else ''
        if expected_workspace_key and request.workspace_key == expected_workspace_key:
            return []
        return [AiDashboardValidationFinding(
            'workspace_boundary_mismatch',
            'Artifact workspace key must match the Metrics provider/profile boundary.',
            'error',
            'workspace_key',
        )]

    def _artifact_validation_result(self, request: DashboardAiArtifactValidationRequest, valid: bool, status: str,
                                    intent_validation: dict) -> dict:
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
        fragments = (
            'password',
            'token',
            'secret',
            'apikey',
            'privatepath',
            'nativequery',
            'nativequerytext',
            'rawquery',
            'providernativequery',
        )
        return normalized == 'sql' or any(fragment in compact for fragment in fragments)
