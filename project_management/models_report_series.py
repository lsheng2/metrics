import uuid

from django.db import models

from project_management.models import Project, ProjectStage


class ReportSeries(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='report_series')
    stage = models.ForeignKey(ProjectStage, on_delete=models.PROTECT, related_name='report_series')
    current_revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class ReportSeriesPolicyRevisionRecord(models.Model):
    series = models.ForeignKey(ReportSeries, on_delete=models.PROTECT, related_name='policy_revisions')
    revision = models.PositiveIntegerField()
    payload_json = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['series', 'revision'], name='pm_report_series_policy_revision_unique'),
        ]
        ordering = ['revision']


class ReportSeriesCommand(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='report_series_commands')
    command = models.UUIDField()
    kind = models.CharField(max_length=40)
    request_hash = models.CharField(max_length=64)
    result_series = models.ForeignKey(ReportSeries, on_delete=models.PROTECT, null=True)
    result_revision = models.PositiveIntegerField(null=True)
    result_hash = models.CharField(max_length=64, blank=True)
    payload_json = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'command'], name='pm_report_series_command_unique'),
        ]


class ReportMeetingChange(models.Model):
    series = models.ForeignKey(ReportSeries, on_delete=models.PROTECT, related_name='meeting_changes')
    revision = models.PositiveIntegerField()
    command = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    payload_json = models.JSONField()
    payload_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ['revision']
        constraints = [
            models.UniqueConstraint(fields=['series', 'revision'], name='pm_meeting_revision_unique'),
            models.UniqueConstraint(fields=['series', 'command'], name='pm_meeting_command_unique'),
        ]
