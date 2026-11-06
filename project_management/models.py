import uuid

from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_subject = models.CharField(max_length=160)
    key = models.CharField(max_length=64)
    name = models.CharField(max_length=160)
    archived = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner_subject', 'key'], name='pm_project_owner_key'),
        ]
        ordering = ['created_at', 'id']


class ProjectStage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='stages')
    key = models.CharField(max_length=64)
    name = models.CharField(max_length=160)
    selection_json = models.JSONField()
    descriptor_json = models.JSONField()
    definition_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'key'], name='pm_stage_project_key'),
        ]
        ordering = ['created_at', 'id']


class ProjectAuditEvent(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='audit_events')
    stage_id = models.UUIDField(null=True)
    kind = models.CharField(max_length=40)
    actor_subject = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)


from project_management.models_report_templates import (
    ReportTemplate,
    ReportTemplateCommand,
    ReportTemplateRevisionRecord,
    ReportTemplateUsage,
    ReportTemplateUse,
)
from project_management.models_report_series import (
    ReportSeries,
    ReportSeriesCommand,
    ReportSeriesPolicyRevisionRecord,
)
