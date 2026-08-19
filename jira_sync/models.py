from django.db import models

from bug_metrics.models import JiraScopeConfig


class JiraSyncCursor(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    )

    scope = models.OneToOneField(JiraScopeConfig, on_delete=models.CASCADE, related_name='sync_cursor')
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    last_jira_updated_cutoff = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    earliest_reliable_bucket_start = models.DateField(null=True, blank=True)
    latest_reliable_bucket_end = models.DateField(null=True, blank=True)
    changelog_coverage_status = models.CharField(max_length=40, blank=True)
    materialized_config_version_hash = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
