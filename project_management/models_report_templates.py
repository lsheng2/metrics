import uuid

from django.db import models

from project_management.models import Project


class ReportTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='report_templates')
    current_revision = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class ReportTemplateRevisionRecord(models.Model):
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name='revisions')
    revision = models.PositiveIntegerField()
    payload_json = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['template', 'revision'], name='pm_template_revision_unique'),
        ]
        ordering = ['revision']


class ReportTemplateCommand(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='template_commands')
    command = models.UUIDField()
    kind = models.CharField(max_length=40)
    request_hash = models.CharField(max_length=64)
    result_template_id = models.UUIDField(null=True)
    result_revision = models.PositiveIntegerField(null=True)
    result_hash = models.CharField(max_length=64, blank=True)
    payload_json = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'command'], name='pm_template_command_unique'),
        ]


class ReportTemplateUsage(models.Model):
    project = models.OneToOneField(Project, on_delete=models.PROTECT, related_name='template_usage')
    retained_payload_bytes = models.PositiveIntegerField(default=0)
    template_count = models.PositiveIntegerField(default=0)
    revision_count = models.PositiveIntegerField(default=0)


class ReportTemplateUse(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='template_uses')
    command = models.UUIDField()
    draft_id = models.UUIDField()
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name='uses')
    revision = models.PositiveIntegerField()
    revision_hash = models.CharField(max_length=64)
    snapshot_json = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64)
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'command'], name='pm_template_use_unique'),
        ]
