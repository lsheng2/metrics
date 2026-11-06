import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project_management', '0002_report_templates'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportSeries',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('current_revision', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='report_series', to='project_management.project')),
                ('stage', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='report_series', to='project_management.projectstage')),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
        migrations.CreateModel(
            name='ReportSeriesCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command', models.UUIDField()),
                ('kind', models.CharField(max_length=40)),
                ('request_hash', models.CharField(max_length=64)),
                ('result_revision', models.PositiveIntegerField(null=True)),
                ('result_hash', models.CharField(blank=True, max_length=64)),
                ('payload_json', models.JSONField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='report_series_commands', to='project_management.project')),
                ('result_series', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='project_management.reportseries')),
            ],
        ),
        migrations.CreateModel(
            name='ReportSeriesPolicyRevisionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField()),
                ('payload_json', models.JSONField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('series', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='policy_revisions', to='project_management.reportseries')),
            ],
            options={'ordering': ['revision']},
        ),
        migrations.AddConstraint('ReportSeriesCommand', models.UniqueConstraint(fields=('project', 'command'), name='pm_report_series_command_unique')),
        migrations.AddConstraint('ReportSeriesPolicyRevisionRecord', models.UniqueConstraint(fields=('series', 'revision'), name='pm_report_series_policy_revision_unique')),
    ]
