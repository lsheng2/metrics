import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0005_chart_publish_governance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bugtrendauditevent',
            name='scope',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='audit_events', to='bug_metrics.jirascopeconfig'),
        ),
    ]