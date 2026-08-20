import bug_metrics.models
import django.db.models.deletion
from django.db import migrations, models


def create_default_bug_trend_chart(apps, schema_editor):
    evidence_contract_model = apps.get_model('bug_metrics', 'BugTrendEvidenceContract')
    chart_definition_model = apps.get_model('bug_metrics', 'BugTrendChartDefinition')
    contract, _ = evidence_contract_model.objects.get_or_create(
        contract_id='default_bug_trend_bucket_series',
        defaults={
            'capability': 'bucket_series',
            'membership_source': 'bug_trend_bucket_issue',
            'membership_key': 'bucket_id:series_name:issue_key',
            'bucket_dimension': 'bucket_id',
            'series_dimension': 'series_name',
            'ticket_identity': 'jira_issue_key',
            'dedupe_policy': 'visible_range_distinct_issue; bucket_series_membership_grain',
            'time_boundary_policy': 'scope_timezone_inclusive_bucket_dates',
            'allowed_list_filters': ['text', 'status', 'severity', 'owner', 'component'],
            'export_policy': 'run_pinned_current_evidence_result',
        },
    )
    chart_definition_model.objects.get_or_create(
        chart_id='default_bug_trend',
        defaults={
            'chart_version': 1,
            'title': 'Default Bug Trend',
            'renderer_type': 'chartjs',
            'integration_route': 'reference',
            'evidence_contract': contract,
            'status': 'published',
            'enabled': True,
            'built_in': True,
            'created_by': 'system',
            'validation_summary': {'source': 'P0b/P0c reference chart'},
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0002_bugtrendauditevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='BugTrendEvidenceContract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contract_id', models.CharField(max_length=120, unique=True)),
                ('capability', models.CharField(choices=[('bucket_series', 'Bucket series'), ('range_only', 'Range only'), ('summary_only', 'Summary only')], max_length=40)),
                ('membership_source', models.CharField(max_length=120)),
                ('membership_key', models.CharField(max_length=120)),
                ('bucket_dimension', models.CharField(blank=True, max_length=120)),
                ('series_dimension', models.CharField(blank=True, max_length=120)),
                ('ticket_identity', models.CharField(max_length=120)),
                ('dedupe_policy', models.CharField(max_length=240)),
                ('time_boundary_policy', models.CharField(max_length=240)),
                ('allowed_list_filters', models.JSONField(default=bug_metrics.models._empty_list)),
                ('export_policy', models.CharField(max_length=240)),
                ('unsupported_reason', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='BugTrendChartDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chart_id', models.CharField(max_length=120, unique=True)),
                ('chart_version', models.PositiveIntegerField(default=1)),
                ('title', models.CharField(max_length=160)),
                ('renderer_type', models.CharField(max_length=40)),
                ('integration_route', models.CharField(max_length=40)),
                ('status', models.CharField(default='draft', max_length=40)),
                ('enabled', models.BooleanField(default=False)),
                ('built_in', models.BooleanField(default=False)),
                ('created_by', models.CharField(default='system', max_length=120)),
                ('validation_summary', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('evidence_contract', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chart_definitions', to='bug_metrics.bugtrendevidencecontract')),
            ],
            options={
                'indexes': [models.Index(fields=['enabled', 'status', 'chart_id'], name='bug_metrics_enabled_403579_idx')],
            },
        ),
        migrations.RunPython(create_default_bug_trend_chart, migrations.RunPython.noop),
    ]