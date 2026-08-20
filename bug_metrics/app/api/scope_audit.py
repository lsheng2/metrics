from dataclasses import dataclass
from typing import Dict, List

from bug_metrics.models import JiraScopeConfig


@dataclass(slots=True)
class ScopeAuditValue:
    category: str
    value: str
    count: int
    mapped: bool
    mapping_group: str


@dataclass(slots=True)
class ScopeAuditCoverage:
    total_issue_count: int
    created_count: int
    updated_count: int
    resolved_count: int
    status_transition_count: int
    resolution_transition_count: int


@dataclass(slots=True)
class ScopeAudit:
    scope_id: int
    scope_name: str
    config_version_hash: str
    observed_values: List[ScopeAuditValue]
    coverage: ScopeAuditCoverage


class ScopeAuditService:
    def build_scope_audit(self, scope: JiraScopeConfig, facts) -> ScopeAudit:
        return ScopeAudit(
            scope_id=scope.id,
            scope_name=scope.name,
            config_version_hash=scope.config_version_hash,
            observed_values=[self._audit_value(scope, item) for item in facts.observed_values],
            coverage=ScopeAuditCoverage(
                total_issue_count=facts.coverage.total_issue_count,
                created_count=facts.coverage.created_count,
                updated_count=facts.coverage.updated_count,
                resolved_count=facts.coverage.resolved_count,
                status_transition_count=facts.coverage.status_transition_count,
                resolution_transition_count=facts.coverage.resolution_transition_count,
            ),
        )

    def _audit_value(self, scope: JiraScopeConfig, observed_value) -> ScopeAuditValue:
        mapped, mapping_group = self._audit_mapping(scope, observed_value.category, observed_value.value)
        return ScopeAuditValue(
            category=observed_value.category,
            value=observed_value.value,
            count=observed_value.count,
            mapped=mapped,
            mapping_group=mapping_group,
        )

    def _audit_mapping(self, scope: JiraScopeConfig, category: str, value: str):
        if category == 'issue_type':
            return self._matches_config_values(value, scope.bug_type_values, 'bug_type')
        if category == 'status':
            status_groups = {
                'open_status': scope.open_status_values,
                'fixed_status': scope.fixed_status_values,
                'closed_status': scope.closed_status_values,
                'terminal_excluded_status': scope.terminal_excluded_status_values,
                'reopen_status': scope.reopen_status_values,
            }
            return self._matches_config_value_groups(value, status_groups)
        if category == 'resolution':
            resolution_groups = {
                'fixed_resolution': scope.fixed_resolution_values,
                'closed_resolution': scope.closed_resolution_values,
            }
            return self._matches_config_value_groups(value, resolution_groups)
        if category == 'severity':
            severity_groups = {
                'critical_high': scope.critical_high_values,
                'medium_low': scope.medium_low_values,
            }
            return self._matches_config_value_groups(value, severity_groups) if scope.severity_field else (False, '')
        if category == 'component':
            return (bool(scope.component_field), 'component_field' if scope.component_field else '')
        return (False, '')

    def _matches_config_values(self, value: str, configured_values: List[str], mapping_group: str):
        return (value in configured_values, mapping_group if value in configured_values else '')

    def _matches_config_value_groups(self, value: str, value_groups: Dict[str, List[str]]):
        for mapping_group, configured_values in value_groups.items():
            if value in configured_values:
                return (True, mapping_group)
        return (False, '')
