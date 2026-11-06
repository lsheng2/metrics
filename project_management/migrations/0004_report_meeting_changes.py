import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('project_management', '0003_report_series')]

    operations = [
        migrations.CreateModel(
            name='ReportMeetingChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField()),
                ('command', models.UUIDField()),
                ('request_hash', models.CharField(max_length=64)),
                ('payload_json', models.JSONField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('series', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name='meeting_changes', to='project_management.reportseries')),
            ],
            options={
                'ordering': ['revision'],
                'constraints': [
                    models.UniqueConstraint(fields=('series', 'revision'), name='pm_meeting_revision_unique'),
                    models.UniqueConstraint(fields=('series', 'command'), name='pm_meeting_command_unique'),
                ],
            },
        ),
    ]
