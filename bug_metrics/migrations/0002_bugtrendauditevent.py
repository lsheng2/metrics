import bug_metrics.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BugTrendAuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=80)),
                ('actor', models.CharField(max_length=120)),
                ('calculation_run_id', models.CharField(blank=True, max_length=80)),
                ('chart_id', models.CharField(blank=True, max_length=120)),
                ('request_summary', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('result', models.CharField(default='success', max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('scope', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_events', to='bug_metrics.jirascopeconfig')),
            ],
            options={
                'indexes': [models.Index(fields=['event_type', 'scope', 'created_at'], name='bug_metrics_event_t_b83fc9_idx')],
            },
        ),
    ]