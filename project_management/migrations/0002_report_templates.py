import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project_management', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('current_revision', models.PositiveIntegerField(default=0)),
                ('archived', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='report_templates', to='project_management.project')),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
        migrations.CreateModel(
            name='ReportTemplateUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('retained_payload_bytes', models.PositiveIntegerField(default=0)),
                ('template_count', models.PositiveIntegerField(default=0)),
                ('revision_count', models.PositiveIntegerField(default=0)),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='template_usage', to='project_management.project')),
            ],
        ),
        migrations.CreateModel(
            name='ReportTemplateCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command', models.UUIDField()),
                ('kind', models.CharField(max_length=40)),
                ('request_hash', models.CharField(max_length=64)),
                ('result_template_id', models.UUIDField(null=True)),
                ('result_revision', models.PositiveIntegerField(null=True)),
                ('result_hash', models.CharField(blank=True, max_length=64)),
                ('payload_json', models.JSONField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='template_commands', to='project_management.project')),
            ],
        ),
        migrations.CreateModel(
            name='ReportTemplateRevisionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField()),
                ('payload_json', models.JSONField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='revisions', to='project_management.reporttemplate')),
            ],
            options={'ordering': ['revision']},
        ),
        migrations.CreateModel(
            name='ReportTemplateUse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command', models.UUIDField()),
                ('draft_id', models.UUIDField()),
                ('revision', models.PositiveIntegerField()),
                ('revision_hash', models.CharField(max_length=64)),
                ('snapshot_json', models.JSONField()),
                ('snapshot_hash', models.CharField(max_length=64)),
                ('request_hash', models.CharField(max_length=64)),
                ('selected_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='template_uses', to='project_management.project')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='uses', to='project_management.reporttemplate')),
            ],
        ),
        migrations.AddConstraint('ReportTemplateRevisionRecord', models.UniqueConstraint(fields=('template', 'revision'), name='pm_template_revision_unique')),
        migrations.AddConstraint('ReportTemplateCommand', models.UniqueConstraint(fields=('project', 'command'), name='pm_template_command_unique')),
        migrations.AddConstraint('ReportTemplateUse', models.UniqueConstraint(fields=('project', 'command'), name='pm_template_use_unique')),
    ]
