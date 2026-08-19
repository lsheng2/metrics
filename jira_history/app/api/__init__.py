from jira_history.models import JiraIssue, JiraIssueSnapshot, JiraTransition


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
