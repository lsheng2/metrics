import bug_metrics.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0004_bug_trend_renderer_route_decision'),
    ]

    operations = [
        migrations.AddField(
            model_name='bugtrendchartdefinition',
            name='owner',
            field=models.CharField(default='system', max_length=120),
        ),
        migrations.AddField(
            model_name='bugtrendchartdefinition',
            name='visibility',
            field=models.CharField(default='shared', max_length=40),
        ),
        migrations.CreateModel(
            name='BugTrendChartPublishRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actor', models.CharField(max_length=120)),
                ('governance_mode', models.CharField(max_length=40)),
                ('status', models.CharField(default='pending_approval', max_length=40)),
                ('request_summary', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publish_requests', to='bug_metrics.bugtrendchartdefinition')),
            ],
        ),
    ]