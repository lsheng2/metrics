from django.db import models


class RuntimeAuditEvent(models.Model):
    event_id = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=80)
    occurred_at = models.DateTimeField()
    sequence = models.IntegerField()
    runtime_id = models.CharField(max_length=120)
    principal_id = models.CharField(max_length=200, blank=True)
    app_id = models.CharField(max_length=80, blank=True)
    session_id = models.CharField(max_length=200, blank=True)
    run_id = models.CharField(max_length=200, blank=True)
    tool_call_id = models.CharField(max_length=200, blank=True)
    approval_id = models.CharField(max_length=200, blank=True)
    tool_name = models.CharField(max_length=200, blank=True)
    result_status = models.CharField(max_length=40, blank=True)
    result_code = models.CharField(max_length=120, blank=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('id',)
