import bug_metrics.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0003_bug_trend_chart_catalog'),
    ]

    operations = [
        migrations.CreateModel(
            name='BugTrendRendererRouteDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('renderer_route', models.CharField(max_length=40)),
                ('same_page_evidence_required', models.BooleanField(default=False)),
                ('c_stock_same_page_capable', models.BooleanField(default=False)),
                ('supported_c_stock_capabilities', models.JSONField(default=bug_metrics.models._empty_list)),
                ('trigger_p2c_spike', models.BooleanField(default=False)),
                ('decision_summary', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='renderer_route_decisions', to='bug_metrics.bugtrendchartdefinition')),
            ],
            options={
                'indexes': [models.Index(fields=['chart', 'created_at'], name='bug_metrics_chart_i_2177f2_idx')],
            },
        ),
    ]