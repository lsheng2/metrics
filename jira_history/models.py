from django.db import models

from bug_metrics.models import JiraScopeConfig


def _empty_dict():
    return {}


class JiraIssue(models.Model):
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='jira_issues')
    issue_key = models.CharField(max_length=80)
    summary = models.TextField(blank=True)
    issue_type = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=120, blank=True)
    resolution_value = models.CharField(max_length=120, blank=True)
    severity_value = models.CharField(max_length=120, blank=True)
    component_value = models.CharField(max_length=240, blank=True)
    owner_value = models.CharField(max_length=240, blank=True)
    team_value = models.CharField(max_length=240, blank=True)
    milestone_value = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    raw_fields_json = models.JSONField(default=_empty_dict)
    is_in_current_scope = models.BooleanField(default=True)

    class Meta:
        unique_together = ('scope', 'issue_key')
        indexes = [
            models.Index(fields=['scope', 'issue_key']),
            models.Index(fields=['scope', 'is_in_current_scope']),
            models.Index(fields=['scope', 'created_at']),
            models.Index(fields=['scope', 'resolved_at']),
        ]


class JiraIssueSnapshot(models.Model):
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='jira_issue_snapshots')
    issue_key = models.CharField(max_length=80)
    synced_at = models.DateTimeField(auto_now_add=True)
    jira_updated_at = models.DateTimeField()
    payload_hash = models.CharField(max_length=64)
    payload_json = models.JSONField(default=_empty_dict)

    class Meta:
        unique_together = ('scope', 'issue_key', 'payload_hash')
        indexes = [
            models.Index(fields=['scope', 'issue_key', 'jira_updated_at']),
        ]


class JiraTransition(models.Model):
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='jira_transitions')
    issue_key = models.CharField(max_length=80)
    transitioned_at = models.DateTimeField()
    field = models.CharField(max_length=120)
    from_value = models.CharField(max_length=240, blank=True)
    to_value = models.CharField(max_length=240, blank=True)

    class Meta:
        unique_together = ('scope', 'issue_key', 'transitioned_at', 'field', 'from_value', 'to_value')
        indexes = [
            models.Index(fields=['scope', 'issue_key', 'transitioned_at']),
            models.Index(fields=['scope', 'field', 'to_value']),
        ]
