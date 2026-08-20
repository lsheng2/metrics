import bug_metrics.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0006_audit_event_optional_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='bugtrendchartdefinition',
            name='chart_spec',
            field=models.JSONField(default=bug_metrics.models._empty_dict),
        ),
    ]