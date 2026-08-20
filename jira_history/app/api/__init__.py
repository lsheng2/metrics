from dataclasses import dataclass
from typing import List

from jira_history.models import JiraIssue, JiraIssueSnapshot, JiraTransition


@dataclass(slots=True)
class ScopeAuditObservedValue:
    category: str
    value: str
    count: int


@dataclass(slots=True)
class ScopeAuditCoverage:
    total_issue_count: int
    created_count: int
    updated_count: int
    resolved_count: int
    status_transition_count: int
    resolution_transition_count: int


@dataclass(slots=True)
class ScopeAuditFacts:
    observed_values: List[ScopeAuditObservedValue]
    coverage: ScopeAuditCoverage


class ApiForJiraHistory:
    def clear_current_scope_state(self, scope):
        JiraTransition.objects.filter(scope=scope).delete()
        JiraIssue.objects.filter(scope=scope).delete()

    def list_issues(self, scope):
        return list(JiraIssue.objects.filter(scope=scope, is_in_current_scope=True))

    def list_tracked_issue_keys(self, scope):
        return list(JiraIssue.objects.filter(scope=scope).values_list('issue_key', flat=True))

    def list_status_resolution_transitions(self, scope):
        return list(JiraTransition.objects.filter(scope=scope, field__in=['status', 'resolution']))

    def get_scope_audit_facts(self, scope) -> ScopeAuditFacts:
        issues = JiraIssue.objects.filter(scope=scope, is_in_current_scope=True)
        transitions = JiraTransition.objects.filter(scope=scope, field__in=['status', 'resolution'])
        observed_values = self._merge_observed_values([
            self._field_value_counts('issue_type', issues.values_list('issue_type', flat=True)),
            self._field_value_counts('status', issues.values_list('status', flat=True)),
            self._field_value_counts('resolution', issues.values_list('resolution_value', flat=True)),
            self._field_value_counts('severity', issues.values_list('severity_value', flat=True)),
            self._field_value_counts('component', issues.values_list('component_value', flat=True)),
            self._transition_value_counts('status', transitions.filter(field='status')),
            self._transition_value_counts('resolution', transitions.filter(field='resolution')),
        ])
        return ScopeAuditFacts(
            sorted(observed_values, key=lambda item: (item.category, item.value)),
            ScopeAuditCoverage(
                total_issue_count=issues.count(),
                created_count=issues.exclude(created_at__isnull=True).count(),
                updated_count=issues.exclude(updated_at__isnull=True).count(),
                resolved_count=issues.exclude(resolved_at__isnull=True).count(),
                status_transition_count=transitions.filter(field='status').count(),
                resolution_transition_count=transitions.filter(field='resolution').count(),
            ),
        )

    def _field_value_counts(self, category: str, values) -> List[ScopeAuditObservedValue]:
        counts = {}
        for value in values:
            if value:
                counts[value] = counts.get(value, 0) + 1
        return [ScopeAuditObservedValue(category, value, count) for value, count in counts.items()]

    def _transition_value_counts(self, category: str, transitions) -> List[ScopeAuditObservedValue]:
        counts = {}
        for transition in transitions:
            for value in [transition.from_value, transition.to_value]:
                if value:
                    counts[value] = counts.get(value, 0) + 1
        return [ScopeAuditObservedValue(category, value, count) for value, count in counts.items()]

    def _merge_observed_values(self, value_groups) -> List[ScopeAuditObservedValue]:
        counts = {}
        for group in value_groups:
            for observed_value in group:
                key = (observed_value.category, observed_value.value)
                counts[key] = counts.get(key, 0) + observed_value.count
        return [ScopeAuditObservedValue(category, value, count) for (category, value), count in counts.items()]

    def upsert_issue(self, scope, issue_key: str, defaults: dict) -> JiraIssue:
        issue, _ = JiraIssue.objects.update_or_create(scope=scope, issue_key=issue_key, defaults=defaults)
        return issue

    def store_snapshot(self, scope, issue_key: str, jira_updated_at, payload_hash: str, payload_json: dict) -> JiraIssueSnapshot:
        snapshot, _ = JiraIssueSnapshot.objects.get_or_create(
            scope=scope,
            issue_key=issue_key,
            payload_hash=payload_hash,
            defaults={'jira_updated_at': jira_updated_at, 'payload_json': payload_json},
        )
        return snapshot

    def store_transition(self, scope, issue_key: str, transitioned_at, field: str, from_value: str, to_value: str) -> JiraTransition:
        transition, _ = JiraTransition.objects.get_or_create(
            scope=scope,
            issue_key=issue_key,
            transitioned_at=transitioned_at,
            field=field,
            from_value=from_value or '',
            to_value=to_value or '',
        )
        return transition


jira_history_api = ApiForJiraHistory()
