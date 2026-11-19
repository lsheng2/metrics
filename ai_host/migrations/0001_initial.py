from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RuntimeAuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(max_length=120, unique=True)),
                ('category', models.CharField(max_length=80)),
                ('occurred_at', models.DateTimeField()),
                ('sequence', models.IntegerField()),
                ('runtime_id', models.CharField(max_length=120)),
                ('principal_id', models.CharField(blank=True, max_length=200)),
                ('app_id', models.CharField(blank=True, max_length=80)),
                ('session_id', models.CharField(blank=True, max_length=200)),
                ('run_id', models.CharField(blank=True, max_length=200)),
                ('tool_call_id', models.CharField(blank=True, max_length=200)),
                ('approval_id', models.CharField(blank=True, max_length=200)),
                ('tool_name', models.CharField(blank=True, max_length=200)),
                ('result_status', models.CharField(blank=True, max_length=40)),
                ('result_code', models.CharField(blank=True, max_length=120)),
                ('payload', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ('id',)},
        ),
    ]
