import hashlib
import json
import uuid

from django.db import models


def _empty_list():
    return []


def _empty_dict():
    return {}


class JiraScopeConfig(models.Model):
    GRANULARITY_DAILY = 'daily'
    GRANULARITY_WEEKLY = 'weekly'

    GRANULARITY_CHOICES = (
        (GRANULARITY_DAILY, 'Daily'),
        (GRANULARITY_WEEKLY, 'Weekly'),
    )

    name = models.CharField(max_length=120, unique=True)
    ip = models.CharField(max_length=120, blank=True)
    project_label = models.CharField(max_length=120, blank=True)
    jql = models.TextField()
    bug_type_values = models.JSONField(default=_empty_list)
    open_status_values = models.JSONField(default=_empty_list)
    fixed_status_values = models.JSONField(default=_empty_list)
    closed_status_values = models.JSONField(default=_empty_list)
    terminal_excluded_status_values = models.JSONField(default=_empty_list)
    fixed_resolution_values = models.JSONField(default=_empty_list)
    closed_resolution_values = models.JSONField(default=_empty_list)
    reopen_status_values = models.JSONField(default=_empty_list)
    severity_field = models.CharField(max_length=120, blank=True)
    critical_high_values = models.JSONField(default=_empty_list)
    medium_low_values = models.JSONField(default=_empty_list)
    component_field = models.CharField(max_length=120, blank=True)
    owner_field = models.CharField(max_length=120, blank=True, default='assignee')
    team_field = models.CharField(max_length=120, blank=True)
    milestone_field = models.CharField(max_length=120, blank=True)
    fix_version_field = models.CharField(max_length=120, blank=True)
    package_version_field = models.CharField(max_length=120, blank=True)
    display_fields = models.JSONField(default=_empty_list)
    timezone = models.CharField(max_length=80, default='UTC')
    bucket_granularity = models.CharField(max_length=20, choices=GRANULARITY_CHOICES, default=GRANULARITY_WEEKLY)
    enabled = models.BooleanField(default=True)
    config_version_hash = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.config_version_hash = self.calculate_config_version_hash()
        super().save(*args, **kwargs)

    def calculate_config_version_hash(self) -> str:
        payload = {
            'jql': self.jql,
            'bug_type_values': self.bug_type_values,
            'open_status_values': self.open_status_values,
            'fixed_status_values': self.fixed_status_values,
            'closed_status_values': self.closed_status_values,
            'terminal_excluded_status_values': self.terminal_excluded_status_values,
            'fixed_resolution_values': self.fixed_resolution_values,
            'closed_resolution_values': self.closed_resolution_values,
            'reopen_status_values': self.reopen_status_values,
            'severity_field': self.severity_field,
            'critical_high_values': self.critical_high_values,
            'medium_low_values': self.medium_low_values,
            'component_field': self.component_field,
            'owner_field': self.owner_field,
            'team_field': self.team_field,
            'milestone_field': self.milestone_field,
            'fix_version_field': self.fix_version_field,
            'package_version_field': self.package_version_field,
            'display_fields': self.display_fields,
            'timezone': self.timezone,
            'bucket_granularity': self.bucket_granularity,
        }
        encoded_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(encoded_payload.encode('utf-8')).hexdigest()

    def __str__(self):
        return self.name


class BugTrendCalculationRun(models.Model):
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='calculation_runs')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    config_version_hash = models.CharField(max_length=64)
    source_coverage_start = models.DateField()
    source_coverage_end = models.DateField()
    bucket_granularity = models.CharField(max_length=20, choices=JiraScopeConfig.GRANULARITY_CHOICES)

    class Meta:
        indexes = [
            models.Index(fields=['scope', 'status', 'config_version_hash']),
        ]


class BugTrendBucket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calculation_run = models.ForeignKey(BugTrendCalculationRun, on_delete=models.CASCADE, related_name='buckets')
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='trend_buckets')
    bucket_start = models.DateField()
    bucket_end = models.DateField()
    granularity = models.CharField(max_length=20, choices=JiraScopeConfig.GRANULARITY_CHOICES)
    new_critical_high_count = models.PositiveIntegerField(default=0)
    new_medium_low_count = models.PositiveIntegerField(default=0)
    fixed_or_closed_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    open_critical_high_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('calculation_run', 'bucket_start', 'bucket_end', 'granularity')
        ordering = ('bucket_start',)


class BugTrendBucketIssue(models.Model):
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='trend_bucket_issues')
    bucket = models.ForeignKey(BugTrendBucket, on_delete=models.CASCADE, related_name='issues')
    calculation_run = models.ForeignKey(BugTrendCalculationRun, on_delete=models.CASCADE, related_name='bucket_issues')
    series_name = models.CharField(max_length=80)
    issue_key = models.CharField(max_length=80)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=120, blank=True)
    severity_value = models.CharField(max_length=120, blank=True)
    owner_value = models.CharField(max_length=240, blank=True)
    component_value = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    extra_fields_json = models.JSONField(default=_empty_dict)

    class Meta:
        unique_together = ('bucket', 'series_name', 'issue_key')
        indexes = [
            models.Index(fields=['calculation_run', 'bucket', 'series_name']),
        ]


class BugTrendAuditEvent(models.Model):
    EVENT_EVIDENCE_EXPORTED = 'evidence_exported'

    event_type = models.CharField(max_length=80)
    actor = models.CharField(max_length=120)
    scope = models.ForeignKey(JiraScopeConfig, on_delete=models.CASCADE, related_name='audit_events', null=True, blank=True)
    calculation_run_id = models.CharField(max_length=80, blank=True)
    chart_id = models.CharField(max_length=120, blank=True)
    request_summary = models.JSONField(default=_empty_dict)
    result = models.CharField(max_length=40, default='success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'scope', 'created_at']),
        ]


class BugTrendEvidenceContract(models.Model):
    CAPABILITY_BUCKET_SERIES = 'bucket_series'
    CAPABILITY_RANGE_ONLY = 'range_only'
    CAPABILITY_SUMMARY_ONLY = 'summary_only'

    CAPABILITY_CHOICES = (
        (CAPABILITY_BUCKET_SERIES, 'Bucket series'),
        (CAPABILITY_RANGE_ONLY, 'Range only'),
        (CAPABILITY_SUMMARY_ONLY, 'Summary only'),
    )

    contract_id = models.CharField(max_length=120, unique=True)
    capability = models.CharField(max_length=40, choices=CAPABILITY_CHOICES)
    membership_source = models.CharField(max_length=120)
    membership_key = models.CharField(max_length=120)
    bucket_dimension = models.CharField(max_length=120, blank=True)
    series_dimension = models.CharField(max_length=120, blank=True)
    ticket_identity = models.CharField(max_length=120)
    dedupe_policy = models.CharField(max_length=240)
    time_boundary_policy = models.CharField(max_length=240)
    allowed_list_filters = models.JSONField(default=_empty_list)
    export_policy = models.CharField(max_length=240)
    unsupported_reason = models.TextField(blank=True)

    def __str__(self):
        return self.contract_id


class BugTrendChartDefinition(models.Model):
    RENDERER_CHARTJS = 'chartjs'
    RENDERER_GRAFANA = 'grafana'
    RENDERER_STATIC_IMAGE = 'static_image'

    ROUTE_REFERENCE = 'reference'
    ROUTE_C_STOCK = 'c_stock'
    ROUTE_C_PLUGIN = 'c_plugin'

    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_DISABLED = 'disabled'

    chart_id = models.CharField(max_length=120, unique=True)
    chart_version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=160)
    renderer_type = models.CharField(max_length=40)
    integration_route = models.CharField(max_length=40)
    evidence_contract = models.ForeignKey(BugTrendEvidenceContract, on_delete=models.PROTECT, related_name='chart_definitions')
    status = models.CharField(max_length=40, default=STATUS_DRAFT)
    enabled = models.BooleanField(default=False)
    built_in = models.BooleanField(default=False)
    created_by = models.CharField(max_length=120, default='system')
    owner = models.CharField(max_length=120, default='system')
    visibility = models.CharField(max_length=40, default='shared')
    validation_summary = models.JSONField(default=_empty_dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['enabled', 'status', 'chart_id']),
        ]

    def __str__(self):
        return self.chart_id


class BugTrendRendererRouteDecision(models.Model):
    chart = models.ForeignKey(BugTrendChartDefinition, on_delete=models.CASCADE, related_name='renderer_route_decisions')
    renderer_route = models.CharField(max_length=40)
    same_page_evidence_required = models.BooleanField(default=False)
    c_stock_same_page_capable = models.BooleanField(default=False)
    supported_c_stock_capabilities = models.JSONField(default=_empty_list)
    trigger_p2c_spike = models.BooleanField(default=False)
    decision_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['chart', 'created_at']),
        ]


class BugTrendChartPublishRequest(models.Model):
    STATUS_PENDING = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    chart = models.ForeignKey(BugTrendChartDefinition, on_delete=models.CASCADE, related_name='publish_requests')
    actor = models.CharField(max_length=120)
    governance_mode = models.CharField(max_length=40)
    status = models.CharField(max_length=40, default=STATUS_PENDING)
    request_summary = models.JSONField(default=_empty_dict)
    created_at = models.DateTimeField(auto_now_add=True)
