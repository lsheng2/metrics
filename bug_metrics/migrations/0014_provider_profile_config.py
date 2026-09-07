from django.db import migrations, models

import bug_metrics.models


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0013_scope_provider_binding'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProviderProfileConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('profile_id', models.CharField(max_length=120, unique=True)),
                ('provider_id', models.CharField(max_length=80)),
                ('display_name', models.CharField(max_length=160)),
                ('lifecycle_state', models.CharField(choices=[('draft', 'Draft'), ('enabled', 'Enabled'), ('archived', 'Archived')], default='draft', max_length=40)),
                ('source_population', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('scope_labels', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('field_bindings', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('value_mappings', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('chart_bindings', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('sync_policy', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('readiness_policy', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('mapping_version', models.PositiveIntegerField(default=1)),
                ('mapping_version_hash', models.CharField(editable=False, max_length=64)),
                ('source_version_hash', models.CharField(editable=False, max_length=64)),
                ('provenance', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='providerprofileconfig',
            index=models.Index(fields=['provider_id', 'lifecycle_state'], name='bug_metrics_provide_ea1ce6_idx'),
        ),
    ]
