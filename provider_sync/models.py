import uuid

from django.db import models


def _empty_dict():
    return {}


def _empty_list():
    return []


class ProviderFactSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_id = models.CharField(max_length=80)
    profile_id = models.CharField(max_length=160)
    source_query_ref = models.CharField(max_length=240, blank=True)
    source_query_hash = models.CharField(max_length=64, blank=True)
    source_query_json = models.JSONField(default=_empty_dict)
    field_set_hash = models.CharField(max_length=64, blank=True)
    mapping_version_hash = models.CharField(max_length=64, blank=True)
    raw_payload_json = models.JSONField(default=_empty_dict)
    freshness_status = models.CharField(max_length=80)
    status = models.CharField(max_length=40, default='completed')
    record_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['provider_id', 'profile_id', 'status', 'completed_at']),
            models.Index(fields=['provider_id', 'profile_id', 'source_query_ref']),
        ]


class ProviderFact(models.Model):
    snapshot = models.ForeignKey(ProviderFactSnapshot, on_delete=models.CASCADE, related_name='facts')
    provider_id = models.CharField(max_length=80)
    profile_id = models.CharField(max_length=160)
    source_item_id = models.CharField(max_length=160)
    source_item_revision = models.CharField(max_length=80, blank=True)
    canonical_fields_json = models.JSONField(default=_empty_dict)
    project_fields_json = models.JSONField(default=_empty_dict)
    field_values_json = models.JSONField(default=_empty_dict)
    provider_fields_json = models.JSONField(default=_empty_dict)
    mapping_version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('snapshot', 'source_item_id', 'source_item_revision')
        indexes = [
            models.Index(fields=['provider_id', 'profile_id', 'source_item_id']),
        ]


class ProviderAggregateArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(ProviderFactSnapshot, on_delete=models.CASCADE, related_name='aggregate_artifacts')
    provider_id = models.CharField(max_length=80)
    profile_id = models.CharField(max_length=160)
    chart_id = models.CharField(max_length=120)
    chart_version = models.PositiveIntegerField(default=1)
    begin_ww = models.CharField(max_length=20)
    end_ww = models.CharField(max_length=20)
    range_mode = models.CharField(max_length=20, default='ww', blank=True)
    range_start = models.CharField(max_length=20, blank=True)
    range_end = models.CharField(max_length=20, blank=True)
    range_grain = models.CharField(max_length=20, blank=True)
    range_label_start = models.CharField(max_length=40, blank=True)
    range_label_end = models.CharField(max_length=40, blank=True)
    cache_identity_hash = models.CharField(max_length=64)
    freshness_status = models.CharField(max_length=80)
    status = models.CharField(max_length=40, default='supported')
    reason = models.TextField(blank=True)
    rows_json = models.JSONField(default=_empty_list)
    grafana_rows_json = models.JSONField(default=_empty_list)
    source_population_json = models.JSONField(default=_empty_dict)
    run_metadata_json = models.JSONField(default=_empty_dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            'provider_id',
            'profile_id',
            'chart_id',
            'chart_version',
            'begin_ww',
            'end_ww',
            'cache_identity_hash',
        )
        indexes = [
            models.Index(fields=['provider_id', 'profile_id', 'chart_id', 'begin_ww', 'end_ww']),
            models.Index(fields=['provider_id', 'profile_id', 'chart_id', 'range_mode', 'range_start', 'range_end']),
            models.Index(fields=['cache_identity_hash']),
        ]


class ProviderSyncCursor(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CONFIGURATION_REQUIRED = 'configuration_required'

    provider_id = models.CharField(max_length=80)
    profile_id = models.CharField(max_length=160)
    status = models.CharField(max_length=40, default=STATUS_PENDING)
    latest_snapshot = models.ForeignKey(ProviderFactSnapshot, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    error_category = models.CharField(max_length=80, blank=True)
    source_query_ref = models.CharField(max_length=240, blank=True)
    source_query_hash = models.CharField(max_length=64, blank=True)
    field_set_hash = models.CharField(max_length=64, blank=True)
    mapping_version_hash = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('provider_id', 'profile_id')
        indexes = [
            models.Index(fields=['provider_id', 'profile_id', 'status']),
        ]
