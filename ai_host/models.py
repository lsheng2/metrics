from django.db import models


class RuntimeAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError('Runtime audit records are append-only.')

    def delete(self):
        raise ValueError('Runtime audit records are append-only.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError('Runtime audit records are append-only.')

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        if update_conflicts:
            raise ValueError('Runtime audit records are append-only.')
        return super().bulk_create(
            objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts,
            update_conflicts=False, update_fields=update_fields, unique_fields=unique_fields,
        )


class RuntimeAuditEvent(models.Model):
    objects = RuntimeAuditQuerySet.as_manager()

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

    def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self._state.adding or force_update or update_fields is not None:
            raise ValueError('Runtime audit records are append-only.')
        return super().save(force_insert=True, using=using)

    def delete(self, *args, **kwargs):
        raise ValueError('Runtime audit records are append-only.')

    class Meta:
        ordering = ('id',)
