import uuid

from django.db import models


class AiChartPublication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool_call_id = models.CharField(max_length=200, unique=True)
    approval_id = models.CharField(max_length=200)
    run_id = models.CharField(max_length=200)
    decided_by = models.CharField(max_length=200)
    decided_at = models.DateTimeField()
    preview_digest = models.CharField(max_length=64)
    data_fingerprint = models.CharField(max_length=64)
    normalized_render_config = models.JSONField()
    provider_id = models.CharField(max_length=80)
    profile_id = models.CharField(max_length=160)
    chart_id = models.CharField(max_length=160)
    chart_version = models.PositiveIntegerField()
    requested_series = models.JSONField()
    range_mode = models.CharField(max_length=8)
    range_start = models.CharField(max_length=40)
    range_end = models.CharField(max_length=40)
    dashboard_uid = models.CharField(max_length=40)
    title = models.TextField()
    visualization = models.CharField(max_length=80)
    grafana_base_url = models.URLField(max_length=2048)
    grafana_url = models.URLField(max_length=2048, blank=True)
    correlation_id = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=(('published', 'Published'), ('failed', 'Failed')))
    error_code = models.CharField(max_length=120, blank=True)
    supersedes = models.OneToOneField(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='superseded_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [models.Index(fields=('dashboard_uid', 'status'), name='ai_chart_target_status')]
